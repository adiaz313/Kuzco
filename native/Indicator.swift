// Display-only AppKit perimeter glow. Input remains one assistant state per line.
import AppKit

final class PerimeterGlow: NSView {
    private var timer: Timer?
    private var tint = [0.65, 1.0, 0.0]
    private var fromTint = [0.65, 1.0, 0.0]
    private var targetTint = [0.65, 1.0, 0.0]
    private var opacity = 0.0
    private var fromOpacity = 0.0
    private var targetOpacity = 0.0
    private var changed = ProcessInfo.processInfo.systemUptime
    private let started = ProcessInfo.processInfo.systemUptime
    override var isOpaque: Bool { false }

    func show(_ state: String) {
        let colors: [String: [Double]] = [
            "LISTENING": [0.65, 1.0, 0.0],
            "THINKING": [0.66, 0.28, 1.0],
            "SPEAKING": [0.15, 0.55, 1.0]]
        guard state == "IDLE" || colors[state] != nil else { return }
        update()
        fromTint = tint
        targetTint = colors[state] ?? tint
        fromOpacity = opacity
        targetOpacity = state == "IDLE" ? 0 : 1
        changed = ProcessInfo.processInfo.systemUptime
        if state != "IDLE" { window?.orderFrontRegardless() }
        if timer == nil && (targetOpacity > 0 || opacity > 0) {
            timer = Timer(timeInterval: 1.0 / 24.0, repeats: true) { [weak self] _ in
                self?.update()
            }
            RunLoop.main.add(timer!, forMode: .common)
        }
        needsDisplay = true
    }

    private func update() {
        let elapsed = ProcessInfo.processInfo.systemUptime - changed
        let progress = min(1.0, elapsed / 0.28)
        let blend = progress * progress * (3 - 2 * progress)
        tint = zip(fromTint, targetTint).map { $0 + ($1 - $0) * blend }
        opacity = fromOpacity + (targetOpacity - fromOpacity) * blend
        needsDisplay = true
        if progress == 1 && targetOpacity == 0 {
            window?.orderOut(nil)
            timer?.invalidate()
            timer = nil  // No animation work while idle.
        }
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.clear(bounds)
        guard opacity > 0 else { return }
        let w = bounds.width - 2, h = bounds.height - 2
        guard w > 0 && h > 0 else { return }
        let perimeter = 2 * (w + h)
        func point(_ fraction: Double) -> CGPoint {
            let d = fraction * perimeter
            if d <= w { return CGPoint(x: 1 + d, y: 1) }
            if d <= w + h { return CGPoint(x: 1 + w, y: 1 + d - w) }
            if d <= 2 * w + h { return CGPoint(x: 1 + 2 * w + h - d, y: 1 + h) }
            return CGPoint(x: 1, y: 1 + perimeter - d)
        }
        let time = ProcessInfo.processInfo.systemUptime - started
        let space = CGColorSpaceCreateDeviceRGB()
        func gradient(_ peak: Double) -> CGGradient {
            let stops: [CGFloat] = [0, 0.15, 0.5, 1]
            let colors = [peak, peak * 0.48, peak * 0.09, 0].map {
                NSColor(srgbRed: tint[0], green: tint[1], blue: tint[2],
                        alpha: $0 * opacity * 1.5625).cgColor // 25% above RC baseline 1.25.
            }
            return CGGradient(colorsSpace: space, colors: colors as CFArray, locations: stops)!
        }
        // Continuous gradients avoid segmented strokes or a hard inner border.
        // Only the outer 18 points contain light; the center is untouched.
        let base = gradient(0.22)
        for (start, end) in [
            (CGPoint(x: 0, y: 0), CGPoint(x: 0, y: 14)),
            (CGPoint(x: 0, y: bounds.height), CGPoint(x: 0, y: bounds.height - 14)),
            (CGPoint(x: 0, y: 0), CGPoint(x: 14, y: 0)),
            (CGPoint(x: bounds.width, y: 0), CGPoint(x: bounds.width - 14, y: 0))] {
            context.drawLinearGradient(base, start: start, end: end, options: [])
        }
        // Long, soft pools of light drift slowly around all four sides.
        for index in 0..<12 {
            let fraction = (Double(index) / 12 + time * 0.004).truncatingRemainder(dividingBy: 1)
            let location = point(fraction)
            let d = fraction * perimeter
            let horizontal = d <= w || (d >= w + h && d <= 2 * w + h)
            let length = 150 + 50 * sin(time * 0.12 + Double(index))
            let brightness = 0.24 + 0.08 * sin(time * 0.18 + Double(index) * 1.7)
            context.saveGState()
            context.translateBy(x: location.x, y: location.y)
            context.scaleBy(x: horizontal ? length : 17, y: horizontal ? 17 : length)
            context.drawRadialGradient(gradient(brightness), startCenter: .zero, startRadius: 0,
                                       endCenter: .zero, endRadius: 1, options: [])
            context.restoreGState()
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
func displayFrame() -> NSRect {
    let builtin = NSScreen.screens.first { screen in
        guard let number = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber else { return false }
        return CGDisplayIsBuiltin(number.uint32Value) != 0
    }
    return (builtin ?? NSScreen.main ?? NSScreen.screens.first)?.frame
        ?? NSRect(x: 0, y: 0, width: 1024, height: 768)
}
let panel = NSPanel(contentRect: displayFrame(), styleMask: [.borderless, .nonactivatingPanel],
                    backing: .buffered, defer: false)
panel.isOpaque = false
panel.backgroundColor = .clear
panel.hasShadow = false
panel.level = .statusBar
panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
panel.ignoresMouseEvents = true
panel.hidesOnDeactivate = false
let glow = PerimeterGlow(frame: NSRect(origin: .zero, size: panel.frame.size))
glow.autoresizingMask = [.width, .height]
panel.contentView = glow
let observer = NotificationCenter.default.addObserver(
    forName: NSApplication.didChangeScreenParametersNotification, object: nil, queue: .main) { _ in
        panel.setFrame(displayFrame(), display: true)
    }
DispatchQueue.global(qos: .userInitiated).async {
    while let line = readLine() {
        DispatchQueue.main.async {
            glow.show(line)
            // Acknowledge after the short transition for optional native smoke checks.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                let status = "\(line) visible=\(panel.isVisible) key=\(panel.isKeyWindow) clickThrough=\(panel.ignoresMouseEvents)\n"
                FileHandle.standardOutput.write(Data(status.utf8))
            }
        }
    }
    DispatchQueue.main.async { app.terminate(nil) } // Also handles Python crash/pipe EOF.
}
app.run()
