// Minimal permission/lifecycle host. Python still owns all assistant behavior.
import AppKit
import AVFoundation
import Darwin

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let root = Bundle.main.object(forInfoDictionaryKey: "KuzcoProject") as! String
let dataHome = Bundle.main.object(forInfoDictionaryKey: "KuzcoHome") as! String
let logs = URL(fileURLWithPath: dataHome).appendingPathComponent("logs")
try? FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
func log(_ message: String) {
    let file = logs.appendingPathComponent("launcher.log")
    let old = logs.appendingPathComponent("launcher.log.1")
    if let attrs = try? FileManager.default.attributesOfItem(atPath: file.path),
       let size = attrs[.size] as? NSNumber, size.intValue > 256 * 1024 {
        try? FileManager.default.removeItem(at: old)
        try? FileManager.default.moveItem(at: file, to: old)
    }
    if !FileManager.default.fileExists(atPath: file.path) {
        FileManager.default.createFile(atPath: file.path, contents: nil)
    }
    if let handle = try? FileHandle(forWritingTo: file) {
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        try? handle.write(contentsOf: Data("\(Date()) \(message)\n".utf8))
    }
}
let child = Process()
var stopping = false
func stop() {
    if stopping { return }
    stopping = true
    log("Stop requested")
    if child.isRunning {
        child.terminate()
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
            if child.isRunning { kill(child.processIdentifier, SIGKILL) }
            exit(0)
        }
    } else { exit(0) }
}
signal(SIGTERM, SIG_IGN)
signal(SIGINT, SIG_IGN)
let termination = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
termination.setEventHandler { stop() }
termination.resume()
let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
interrupt.setEventHandler { stop() }
interrupt.resume()
let resumeObserver = NSWorkspace.shared.notificationCenter.addObserver(
    forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { _ in
        log("Mac woke; notifying Python to refresh audio input")
        if child.isRunning { kill(child.processIdentifier, SIGUSR1) }
    }
func startPython() {
    if CommandLine.arguments.contains("--permissions-only") {
        log("Microphone permission setup complete")
        exit(0)
    }
    child.executableURL = URL(fileURLWithPath: root + "/.venv/bin/python")
    child.arguments = ["-u", root + "/background.py"]
    var environment = ProcessInfo.processInfo.environment
    environment["KUZCO_HOME"] = dataHome
    child.environment = environment
    child.currentDirectoryURL = URL(fileURLWithPath: root)
    child.standardInput = FileHandle.nullDevice
    child.standardOutput = FileHandle.nullDevice
    // Unexpected errors before Python logging starts are captured through a bounded pipe.
    let errors = Pipe()
    child.standardError = errors
    errors.fileHandleForReading.readabilityHandler = { handle in
        let data = handle.availableData
        if !data.isEmpty {
            let text = String(decoding: data.prefix(2048), as: UTF8.self)
            DispatchQueue.main.async { log("Python stderr: " + text) }
        }
    }
    child.terminationHandler = { process in
        DispatchQueue.main.async {
            errors.fileHandleForReading.readabilityHandler = nil
            log("Python exited: \(process.terminationStatus), reason: \(process.terminationReason.rawValue)")
            exit(stopping ? 0 : process.terminationStatus)
        }
    }
    do {
        try child.run()
        log("Python started: pid \(child.processIdentifier)")
    } catch {
        log("Cannot start Python: \(error)")
        exit(1)
    }
}
log("Launcher started")
switch AVCaptureDevice.authorizationStatus(for: .audio) {
case .authorized: startPython()
case .notDetermined:
    log("Requesting microphone permission")
    AVCaptureDevice.requestAccess(for: .audio) { granted in
        DispatchQueue.main.async {
            if granted { startPython() }
            else { log("Microphone denied. Enable Kuzco Background in macOS Privacy & Security → Microphone."); exit(78) }
        }
    }
default:
    log("Microphone denied/restricted. Enable Kuzco Background in macOS Privacy & Security → Microphone.")
    exit(78)
}
app.run()
