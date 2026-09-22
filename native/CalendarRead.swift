import Foundation
import EventKit

// Purpose-limited EventKit bridge. There are deliberately no save/remove paths.
struct Request: Decodable {
    let action: String
    let day: String?
    let start_iso: String?
    let end_iso: String?
    let timed_only: Bool?
    let include_location: Bool?
}

func emit(_ value: [String: Any]) {
    if let bytes = try? JSONSerialization.data(withJSONObject: value),
       let text = String(data: bytes, encoding: .utf8) { print(text) }
}

func fail(_ code: String) { emit(["error": code]) }

guard let line = readLine(), let data = line.data(using: .utf8),
      let request = try? JSONDecoder().decode(Request.self, from: data) else {
    fail("invalid_request")
    exit(0)
}

let calendar = Calendar.current
let now = Date()
let start: Date
let end: Date
if request.action == "day" {
    guard let day = request.day,
          day.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil,
          let parsed = calendar.date(from: DateComponents(
            year: Int(day.prefix(4)), month: Int(day.dropFirst(5).prefix(2)),
            day: Int(day.suffix(2)))),
          calendar.dateComponents([.year, .month, .day], from: parsed).year == Int(day.prefix(4)),
          calendar.dateComponents([.year, .month, .day], from: parsed).month == Int(day.dropFirst(5).prefix(2)),
          calendar.dateComponents([.year, .month, .day], from: parsed).day == Int(day.suffix(2)),
          let next = calendar.date(byAdding: .day, value: 1, to: parsed) else {
        fail("invalid_range")
        exit(0)
    }
    start = parsed
    end = next
} else if request.action == "next" {
    start = now
    guard let horizon = calendar.date(byAdding: .day, value: 30, to: now) else {
        fail("invalid_range")
        exit(0)
    }
    end = horizon
} else if request.action == "range" {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    guard let from = request.start_iso.flatMap(formatter.date(from:)),
          let until = request.end_iso.flatMap(formatter.date(from:)),
          until > from, until.timeIntervalSince(from) <= 31 * 86_400 else {
        fail("invalid_range")
        exit(0)
    }
    start = from
    end = until
} else {
    fail("unknown_action")
    exit(0)
}

let store = EKEventStore()
let status = EKEventStore.authorizationStatus(for: .event)
if status == .denied || status == .restricted || status == .writeOnly {
    fail("permission_denied")
    exit(0)
}
if status != .fullAccess {
    var finished = false
    var granted = false
    store.requestFullAccessToEvents { allowed, _ in
        granted = allowed
        finished = true
    }
    let deadline = Date().addingTimeInterval(45)
    while !finished && Date() < deadline {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
    }
    if !finished {
        fail("permission_timeout")
        exit(0)
    }
    if !granted {
        fail("permission_denied")
        exit(0)
    }
}

let events = store.events(matching: store.predicateForEvents(
    withStart: start, end: end, calendars: nil))
    .filter { request.action != "next" || $0.startDate >= now }
    .filter { request.timed_only != true || !$0.isAllDay }
    .sorted { a, b in
        if a.startDate != b.startDate { return a.startDate < b.startDate }
        if a.endDate != b.endDate { return a.endDate < b.endDate }
        return (a.title ?? "") < (b.title ?? "")
    }
let selected = request.action == "next" ? Array(events.prefix(1)) : Array(events.prefix(50))
let formatter = ISO8601DateFormatter()
formatter.formatOptions = [.withInternetDateTime]
let output: [[String: Any]] = selected.map { event in
    var item: [String: Any] = ["title": String((event.title ?? "Untitled event").prefix(200)),
         "start_iso": formatter.string(from: event.startDate),
         "end_iso": formatter.string(from: event.endDate),
         "all_day": event.isAllDay,
         "calendar": String(event.calendar.title.prefix(100))]
    if request.include_location == true {
        item["location"] = String((event.location ?? "").prefix(200))
    }
    return item
}
emit(["events": output, "truncated": events.count > selected.count,
      "start_iso": formatter.string(from: start), "end_iso": formatter.string(from: end)])
