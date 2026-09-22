// Native menu-bar lifecycle host. Python continues to own assistant behavior.
import AppKit
import AVFoundation
import Darwin
import Foundation

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let root = Bundle.main.object(forInfoDictionaryKey: "KuzcoProject") as! String
let dataHome = Bundle.main.object(forInfoDictionaryKey: "KuzcoHome") as! String
let modelPort = Bundle.main.object(forInfoDictionaryKey: "KuzcoPort") as! Int
let modelID = Bundle.main.object(forInfoDictionaryKey: "KuzcoModel") as! String
let logs = URL(fileURLWithPath: dataHome).appendingPathComponent("logs")
let enabledFile = URL(fileURLWithPath: dataHome).appendingPathComponent("config/runtime-enabled")
let runtimeFile = URL(fileURLWithPath: dataHome).appendingPathComponent("runtime-status.json")
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

final class StatusDotView: NSView {
    var color: NSColor = .secondaryLabelColor { didSet { needsDisplay = true } }
    override func draw(_ dirtyRect: NSRect) {
        color.setFill()
        NSBezierPath(ovalIn: bounds.insetBy(dx: 1, dy: 1)).fill()
    }
}

final class StatusMenuView: NSView {
    private let name = NSTextField(labelWithString: "")
    private let value = NSTextField(labelWithString: "")
    private let dot = StatusDotView(frame: NSRect(x: 156, y: 8, width: 8, height: 8))

    init(name title: String) {
        super.init(frame: NSRect(x: 0, y: 0, width: 270, height: 24))
        name.stringValue = title
        name.font = NSFont.menuFont(ofSize: 0)
        name.textColor = .labelColor
        name.frame = NSRect(x: 16, y: 3, width: 134, height: 18)
        value.font = NSFont.menuFont(ofSize: 0)
        value.textColor = .labelColor
        value.frame = NSRect(x: 172, y: 3, width: 90, height: 18)
        addSubview(name)
        addSubview(dot)
        addSubview(value)
    }

    required init?(coder: NSCoder) { nil }

    func set(_ text: String, color: NSColor) {
        value.stringValue = text
        dot.color = color
    }
}

final class KuzcoController: NSObject, NSMenuDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    private let menu = NSMenu()
    private let assistantStatus = StatusMenuView(name: "Kuzco")
    private let wakeStatus = StatusMenuView(name: "Wake Word")
    private let modelStatus = StatusMenuView(name: "Local Model")
    private let toggleSwitch = NSSwitch(frame: NSRect(x: 210, y: 6, width: 42, height: 20))
    private let toggleView = NSView(frame: NSRect(x: 0, y: 0, width: 270, height: 32))
    private lazy var quitItem = NSMenuItem(title: "Quit Kuzco", action: #selector(quitKuzco), keyEquivalent: "q")
    private var child: Process?
    private var errorPipe: Pipe?
    private var enabled = true
    private var plannedStop = false
    private var shuttingDown = false
    private var modelState = "Unavailable"
    private var timer: Timer?

    override init() {
        super.init()
        enabled = loadEnabled()
        configureMenu()
        updateStatus()
        timer = Timer.scheduledTimer(withTimeInterval: 15.0, repeats: true) { [weak self] _ in
            self?.updateStatus()
            self?.refreshModelStatus()
        }
    }

    private func configureMenu() {
        statusItem.button?.toolTip = "Kuzco"
        if let iconURL = Bundle.main.url(forResource: "kuzco-menu-icon-statusbar", withExtension: "png"),
           let icon = NSImage(contentsOf: iconURL) {
            // The emblem has substantial internal detail; 26 points gives it
            // the same optical weight as neighboring menu-bar symbols.
            icon.size = NSSize(width: 26, height: 26)
            icon.isTemplate = false
            statusItem.button?.image = icon
        } else {
            statusItem.button?.title = "K"
        }
        let toggleLabel = NSTextField(labelWithString: "Kuzco Enabled")
        toggleLabel.font = NSFont.menuFont(ofSize: 0)
        toggleLabel.textColor = .labelColor
        toggleLabel.frame = NSRect(x: 16, y: 7, width: 180, height: 18)
        toggleSwitch.controlSize = .small
        toggleSwitch.target = self
        toggleSwitch.action = #selector(toggleEnabled)
        toggleSwitch.setAccessibilityLabel("Kuzco Enabled")
        toggleView.addSubview(toggleLabel)
        toggleView.addSubview(toggleSwitch)
        quitItem.target = self
        for view in [assistantStatus, wakeStatus, modelStatus] {
            let item = NSMenuItem()
            item.view = view
            menu.addItem(item)
        }
        menu.addItem(.separator())
        let toggleItem = NSMenuItem()
        toggleItem.view = toggleView
        menu.addItem(toggleItem)
        menu.addItem(.separator())
        menu.addItem(quitItem)
        menu.delegate = self
        statusItem.menu = menu
    }

    private func loadEnabled() -> Bool {
        guard let value = try? String(contentsOf: enabledFile, encoding: .utf8) else { return true }
        return value.trimmingCharacters(in: .whitespacesAndNewlines) != "off"
    }

    private func saveEnabled() {
        try? FileManager.default.createDirectory(at: enabledFile.deletingLastPathComponent(),
                                                 withIntermediateDirectories: true)
        let temporary = enabledFile.appendingPathExtension("tmp")
        try? (enabled ? "on\n" : "off\n").write(to: temporary, atomically: true, encoding: .utf8)
        try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: temporary.path)
        try? FileManager.default.removeItem(at: enabledFile)
        try? FileManager.default.moveItem(at: temporary, to: enabledFile)
    }

    private var childRunning: Bool { child?.isRunning == true }

    private var wakeListening: Bool {
        guard childRunning,
              let process = child,
              let data = try? Data(contentsOf: runtimeFile),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let pid = object["pid"] as? NSNumber,
              pid.int32Value == process.processIdentifier,
              object["wake_listening"] as? Bool == true else { return false }
        return true
    }

    private func updateStatus() {
        if !enabled { assistantStatus.set("Paused", color: .secondaryLabelColor) }
        else if childRunning { assistantStatus.set("Running", color: .systemGreen) }
        else { assistantStatus.set("Not Running", color: .systemRed) }
        wakeStatus.set(wakeListening ? "On" : "Off",
                       color: wakeListening ? .systemGreen : .secondaryLabelColor)
        if modelState == "Available" { modelStatus.set(modelState, color: .systemGreen) }
        else { modelStatus.set("Unavailable", color: .systemRed) }
        toggleSwitch.state = enabled ? .on : .off
    }

    func menuWillOpen(_ menu: NSMenu) {
        updateStatus()
        refreshModelStatus()
    }

    func startPython() {
        guard enabled, !shuttingDown, !childRunning else { return }
        plannedStop = false
        let process = Process()
        process.executableURL = URL(fileURLWithPath: root + "/.venv/bin/python")
        process.arguments = ["-u", root + "/background.py"]
        var environment = ProcessInfo.processInfo.environment
        environment["KUZCO_HOME"] = dataHome
        process.environment = environment
        process.currentDirectoryURL = URL(fileURLWithPath: root)
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = FileHandle.nullDevice
        let errors = Pipe()
        process.standardError = errors
        errors.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty {
                let text = String(decoding: data.prefix(2048), as: UTF8.self)
                DispatchQueue.main.async { log("Python stderr: " + text) }
            }
        }
        process.terminationHandler = { [weak self, weak process] terminated in
            DispatchQueue.main.async {
                guard let self = self else { return }
                errors.fileHandleForReading.readabilityHandler = nil
                try? FileManager.default.removeItem(at: runtimeFile)
                if self.child === process { self.child = nil; self.errorPipe = nil }
                log("Python exited: \(terminated.terminationStatus), reason: \(terminated.terminationReason.rawValue)")
                self.updateStatus()
                if self.shuttingDown { NSApp.terminate(nil) }
                else if !self.plannedStop && self.enabled { exit(Int32(terminated.terminationStatus)) }
                self.plannedStop = false
            }
        }
        do {
            try process.run()
            child = process
            errorPipe = errors
            log("Python started: pid \(process.processIdentifier)")
            updateStatus()
        } catch {
            errors.fileHandleForReading.readabilityHandler = nil
            log("Cannot start Python: \(error)")
            updateStatus()
        }
    }

    private func stopPython() {
        plannedStop = true
        try? FileManager.default.removeItem(at: runtimeFile)
        guard let process = child, process.isRunning else { child = nil; updateStatus(); return }
        let pid = process.processIdentifier
        process.terminate()
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
            if process.isRunning { kill(pid, SIGKILL) }
        }
        updateStatus()
    }

    @objc private func toggleEnabled() {
        enabled.toggle()
        saveEnabled()
        log(enabled ? "Assistant enabled from menu" : "Assistant paused from menu")
        if enabled { startPython() } else { stopPython() }
        updateStatus()
    }

    func refreshAudioAfterWake() {
        guard enabled, let process = child, process.isRunning else { return }
        log("Mac woke; notifying Python to refresh audio input")
        kill(process.processIdentifier, SIGUSR1)
    }

    private func refreshModelStatus() {
        guard let url = URL(string: "http://127.0.0.1:\(modelPort)/api/v1/models") else { return }
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        URLSession.shared.dataTask(with: request) { [weak self] data, _, _ in
            var next = "Unavailable"
            if let data = data,
               let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let models = object["models"] as? [[String: Any]] {
                for model in models where (model["key"] as? String == modelID || model["id"] as? String == modelID) {
                    next = "Available"
                    break
                }
            }
            DispatchQueue.main.async { self?.modelState = next; self?.updateStatus() }
        }.resume()
    }

    @objc private func quitKuzco() {
        guard !shuttingDown else { return }
        shuttingDown = true
        log("Quit selected; stopping assistant and unloading login job")
        stopPython()
        let command = Process()
        command.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        command.arguments = ["bootout", "gui/\(getuid())/local.kuzco.background"]
        command.standardOutput = FileHandle.nullDevice
        command.standardError = FileHandle.nullDevice
        try? command.run()
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }
    }

    func terminateFromSignal() {
        guard !shuttingDown else { return }
        shuttingDown = true
        log("Stop requested")
        stopPython()
        if !childRunning { NSApp.terminate(nil) }
    }
}

if CommandLine.arguments.contains("--permissions-only") {
    log("Microphone permission setup complete")
    exit(0)
}

let controller = KuzcoController()
signal(SIGTERM, SIG_IGN)
signal(SIGINT, SIG_IGN)
let termination = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
termination.setEventHandler { controller.terminateFromSignal() }
termination.resume()
let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
interrupt.setEventHandler { controller.terminateFromSignal() }
interrupt.resume()
let resumeObserver = NSWorkspace.shared.notificationCenter.addObserver(
    forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { _ in
        controller.refreshAudioAfterWake()
    }

log("Launcher started")
switch AVCaptureDevice.authorizationStatus(for: .audio) {
case .authorized:
    controller.startPython()
case .notDetermined:
    log("Requesting microphone permission")
    AVCaptureDevice.requestAccess(for: .audio) { granted in
        DispatchQueue.main.async {
            if granted { controller.startPython() }
            else { log("Microphone denied. Enable Kuzco Background in macOS Privacy & Security → Microphone.") }
        }
    }
default:
    log("Microphone denied/restricted. Enable Kuzco Background in macOS Privacy & Security → Microphone.")
}
app.run()
