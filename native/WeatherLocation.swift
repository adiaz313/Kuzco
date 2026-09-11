// One weather-only fix per invocation. No background location monitoring/history.
import AppKit
import CoreLocation

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let authorize = CommandLine.arguments.contains("--authorize")

final class WeatherLocation: NSObject, CLLocationManagerDelegate {
    let manager = CLLocationManager()
    var requested = false
    func finish(_ value: [String: Any]) {
        if let data = try? JSONSerialization.data(withJSONObject: value), let text = String(data: data, encoding: .utf8) {
            print(text)
        }
        manager.stopUpdatingLocation()
        exit(0)
    }
    func begin() {
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
        locationManagerDidChangeAuthorization(manager)
    }
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.authorizationStatus {
        case .notDetermined:
            if authorize {
                app.activate(ignoringOtherApps: true)
                manager.requestWhenInUseAuthorization()
            } else { finish(["error": "Allow Kuzco Weather location access using the documented setup command.", "code": "permission_required"]) }
        case .authorizedAlways, .authorizedWhenInUse:
            if authorize { finish(["authorized": true]); return }
            if !requested { requested = true; manager.startUpdatingLocation() }
        default: finish(["error": "Weather location permission is unavailable. Check macOS Location Services.", "code": "permission_denied"])
        }
    }
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let fix = locations.last,
              usableWeatherFix(age: fix.timestamp.timeIntervalSinceNow, accuracy: fix.horizontalAccuracy) else { return }
        // Approximate coordinates suffice for a forecast. Never emit exact GPS precision.
        finish(["latitude": (fix.coordinate.latitude * 100).rounded() / 100,
                "longitude": (fix.coordinate.longitude * 100).rounded() / 100, "label": "current location"])
    }
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // A temporary unknown fix is not a permission failure; allow the same deadline.
        if (error as? CLError)?.code == .locationUnknown { return }
        finish(["error": "Current weather location could not be obtained.", "code": "location_failed"])
    }
}
let delegate = WeatherLocation()
DispatchQueue.main.async { delegate.begin() }
DispatchQueue.main.asyncAfter(deadline: .now() + (authorize ? 60 : 6)) {
    delegate.finish(["error": "Weather location request timed out.", "code": "location_timeout"])
}
app.run()
