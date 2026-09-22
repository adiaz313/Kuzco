import CoreAudio
import Foundation

func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value),
       let text = String(data: data, encoding: .utf8) { print(text) }
}
func property(_ selector: AudioObjectPropertySelector, _ channel: UInt32 = 0) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: selector, mScope: kAudioDevicePropertyScopeOutput, mElement: channel)
}
guard CommandLine.arguments.count == 3 else { emit(["error": "invalid_request"]); exit(0) }
let action = CommandLine.arguments[1]
let value = CommandLine.arguments[2]
var output = AudioObjectID(0)
var size = UInt32(MemoryLayout<AudioObjectID>.size)
var defaultAddress = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultOutputDevice,
    mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &defaultAddress, 0, nil, &size, &output) == noErr,
      output != kAudioObjectUnknown else { emit(["error": "no_output_device"]); exit(0) }
func readScalar(_ channel: UInt32) -> Float32? {
    var address = property(kAudioDevicePropertyVolumeScalar, channel)
    var result: Float32 = 0
    var bytes = UInt32(MemoryLayout<Float32>.size)
    guard AudioObjectHasProperty(output, &address),
          AudioObjectGetPropertyData(output, &address, 0, nil, &bytes, &result) == noErr else { return nil }
    return result
}
func setScalar(_ channel: UInt32, _ value: Float32) -> Bool {
    var address = property(kAudioDevicePropertyVolumeScalar, channel)
    var settable = DarwinBoolean(false)
    guard AudioObjectHasProperty(output, &address),
          AudioObjectIsPropertySettable(output, &address, &settable) == noErr, settable.boolValue else { return false }
    var adjusted = value
    return AudioObjectSetPropertyData(output, &address, 0, nil,
        UInt32(MemoryLayout<Float32>.size), &adjusted) == noErr
}
func readMute() -> Bool? {
    var address = property(kAudioDevicePropertyMute)
    var muted: UInt32 = 0
    var bytes = UInt32(MemoryLayout<UInt32>.size)
    guard AudioObjectHasProperty(output, &address),
          AudioObjectGetPropertyData(output, &address, 0, nil, &bytes, &muted) == noErr else { return nil }
    return muted != 0
}
func setMute(_ mute: Bool) -> Bool {
    var address = property(kAudioDevicePropertyMute)
    var settable = DarwinBoolean(false)
    guard AudioObjectHasProperty(output, &address),
          AudioObjectIsPropertySettable(output, &address, &settable) == noErr, settable.boolValue else { return false }
    var value: UInt32 = mute ? 1 : 0
    return AudioObjectSetPropertyData(output, &address, 0, nil,
        UInt32(MemoryLayout<UInt32>.size), &value) == noErr
}
if action == "mute" {
    guard value == "true" || value == "false" else { emit(["error": "invalid_mute_value"]); exit(0) }
    guard setMute(value == "true") else { emit(["error": "mute_unavailable"]); exit(0) }
    let target = value == "true"
    var verified = readMute() == target
    for _ in 0..<8 where !verified {
        Thread.sleep(forTimeInterval: 0.05)
        verified = readMute() == target
    }
    guard verified else { emit(["error": "mute_change_unverified"]); exit(0) }
    emit(["muted": target])
} else if action == "adjust" || action == "set" {
    let current = readScalar(0) ?? readScalar(1)
    guard let current else { emit(["error": "volume_unavailable"]); exit(0) }
    var desired: Float32
    if action == "adjust" {
        guard value == "up" || value == "down" else { emit(["error": "invalid_direction"]); exit(0) }
        desired = min(1, max(0, current + (value == "up" ? 0.1 : -0.1)))
    } else {
        guard let percent = Int(value), (0...100).contains(percent) else { emit(["error": "invalid_percent"]); exit(0) }
        desired = Float32(percent) / 100
    }
    let success = setScalar(0, desired) || (setScalar(1, desired) && setScalar(2, desired))
    guard success else { emit(["error": "volume_unavailable"]); exit(0) }
    var observed = readScalar(0) ?? readScalar(1)
    for _ in 0..<8 where observed == nil || abs(observed! - desired) > 0.03 {
        Thread.sleep(forTimeInterval: 0.05)
        observed = readScalar(0) ?? readScalar(1)
    }
    guard let observed, abs(observed - desired) <= 0.03 else {
        emit(["error": "volume_change_unverified"]); exit(0)
    }
    emit(["percent": Int((observed * 100).rounded())])
} else {
    emit(["error": "invalid_action"])
}
