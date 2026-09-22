import Foundation
import EventKit

func waitUntil(_ done: () -> Bool, seconds: TimeInterval) -> Bool {
    let deadline = Date().addingTimeInterval(seconds)
    while !done() && Date() < deadline {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
    }
    return done()
}

// Narrow JSON bridge. The Python policy and selection layer decides what may
// happen; this process has no shell, network, or general automation capability.
struct Request: Decodable {
    let action: String
    let title: String?
    let due_iso: String?
    let identifier: String?
}

func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value),
       let text = String(data: data, encoding: .utf8) { print(text) }
}

func fail(_ code: String) {
    emit(["error": code])
}

guard let line = readLine(), let bytes = line.data(using: .utf8),
      let request = try? JSONDecoder().decode(Request.self, from: bytes) else {
    fail("invalid_request")
    exit(0)
}

let store = EKEventStore()
let status = EKEventStore.authorizationStatus(for: .reminder)
if status == .denied || status == .restricted {
    fail("permission_denied")
    exit(0)
}
if status != .fullAccess {
    var finished = false
    var granted = false
    store.requestFullAccessToReminders { allowed, _ in
        granted = allowed
        finished = true
    }
    if !waitUntil({ finished }, seconds: 45) {
        fail("permission_timeout")
        exit(0)
    }
    if !granted {
        fail("permission_denied")
        exit(0)
    }
}

if request.action == "create" {
    guard let title = request.title, !title.isEmpty,
          let calendar = store.defaultCalendarForNewReminders() else {
        fail("reminders_unavailable")
        exit(0)
    }
    let reminder = EKReminder(eventStore: store)
    reminder.title = title
    reminder.calendar = calendar
    if let iso = request.due_iso, !iso.isEmpty {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        guard let date = formatter.date(from: iso), date > Date() else {
            fail("invalid_due_time")
            exit(0)
        }
        reminder.dueDateComponents = Calendar.current.dateComponents(
            [.year, .month, .day, .hour, .minute], from: date)
        reminder.addAlarm(EKAlarm(absoluteDate: date))
    }
    do {
        try store.save(reminder, commit: true)
        emit(["created": true, "identifier": reminder.calendarItemIdentifier,
              "title": title, "due_iso": request.due_iso ?? ""])
    } catch {
        fail("save_failed")
    }
} else if request.action == "list" {
    let predicate = store.predicateForIncompleteReminders(withDueDateStarting: nil,
                                                              ending: nil, calendars: nil)
    var finished = false
    var found: [EKReminder] = []
    store.fetchReminders(matching: predicate) { reminders in
        found = reminders ?? []
        finished = true
    }
    if !waitUntil({ finished }, seconds: 20) {
        fail("read_timeout")
        exit(0)
    }
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    let items: [[String: Any]] = found.prefix(200).map { reminder in
        var item: [String: Any] = ["identifier": reminder.calendarItemIdentifier,
                                   "title": reminder.title ?? ""]
        if let components = reminder.dueDateComponents,
           let date = Calendar.current.date(from: components) {
            item["due_iso"] = formatter.string(from: date)
        }
        return item
    }
    emit(["items": items, "truncated": found.count > 200])
} else if request.action == "complete" || request.action == "remove" {
    guard let identifier = request.identifier,
          let reminder = store.calendarItem(withIdentifier: identifier) as? EKReminder,
          !reminder.isCompleted else {
        fail("reminder_not_found")
        exit(0)
    }
    do {
        if request.action == "complete" {
            reminder.isCompleted = true
            try store.save(reminder, commit: true)
            emit(["completed": true])
        } else {
            try store.remove(reminder, commit: true)
            emit(["removed": true])
        }
    } catch {
        fail("update_failed")
    }
} else {
    fail("unknown_action")
}
