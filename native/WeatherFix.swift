import Foundation

// A rejected cached fix means keep waiting within the caller's deadline, not fail.
func usableWeatherFix(age: Double, accuracy: Double) -> Bool {
    return age.isFinite && accuracy.isFinite && abs(age) < 300 && accuracy >= 0 && accuracy <= 10000
}
