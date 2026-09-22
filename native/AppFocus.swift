import AppKit
import Foundation

// One narrow operation; no generic AppleScript, process execution or app enumeration output.
guard CommandLine.arguments.count == 2 else {
    print("{\"error\":\"invalid_request\"}")
    exit(0)
}
let requested = CommandLine.arguments[1].trimmingCharacters(in: .whitespacesAndNewlines)
guard !requested.isEmpty, requested.count <= 80,
      requested.unicodeScalars.allSatisfy({ CharacterSet.alphanumerics.contains($0) || " .-'".unicodeScalars.contains($0) }) else {
    print("{\"error\":\"invalid_application_name\"}")
    exit(0)
}
let matches = NSWorkspace.shared.runningApplications.filter {
    $0.localizedName?.localizedCaseInsensitiveCompare(requested) == .orderedSame
}
func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value),
       let text = String(data: data, encoding: .utf8) { print(text) }
}
if matches.count == 0 { emit(["error": "not_running"]); exit(0) }
if matches.count > 1 { emit(["error": "ambiguous_application"]); exit(0) }
let app = matches[0]
guard app.activate(options: []) else { emit(["error": "activation_failed"]); exit(0) }
RunLoop.current.run(until: Date().addingTimeInterval(0.2))
emit(["focused": app.isActive])
