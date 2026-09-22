// Bounded Apple MapKit bridge. One request per process; no tracking or history.
import AppKit
import CoreLocation
import Foundation
import MapKit

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

func finish(_ value: [String: Any]) -> Never {
    if let data = try? JSONSerialization.data(withJSONObject: value),
       let text = String(data: data, encoding: .utf8) { print(text) }
    exit(0)
}

func normalized(_ text: String) -> String {
    text.lowercased().components(separatedBy: CharacterSet.alphanumerics.inverted)
        .filter { !$0.isEmpty }.joined(separator: " ")
}

func candidate(_ item: MKMapItem, origin: CLLocation? = nil) -> [String: Any] {
    var value: [String: Any] = [
        "name": item.name ?? "Unknown place",
        "address": item.placemark.title ?? "",
        "latitude": item.placemark.coordinate.latitude,
        "longitude": item.placemark.coordinate.longitude,
        "source": "Apple MapKit"
    ]
    if let id = item.identifier?.rawValue { value["provider_id"] = id }
    if let city = item.placemark.locality { value["city"] = city }
    if let category = item.pointOfInterestCategory?.rawValue { value["category"] = category }
    if let phone = item.phoneNumber { value["phone"] = phone }
    if let url = item.url?.absoluteString { value["website"] = url }
    if let origin = origin, let location = item.placemark.location {
        value["distance_meters"] = origin.distance(from: location)
    }
    return value
}

func search(_ query: String, region: MKCoordinateRegion? = nil,
            completion: @escaping ([MKMapItem]?, String?) -> Void) {
    let normalizedQuery = normalized(query)
    let operation: MKLocalSearch
    if let region = region,
       ["coffee", "coffee shop", "cafe", "restaurant"].contains(normalizedQuery) {
        let request = MKLocalPointsOfInterestRequest(coordinateRegion: region)
        request.pointOfInterestFilter = MKPointOfInterestFilter(including:
            normalizedQuery == "restaurant" ? [.restaurant] : [.cafe])
        operation = MKLocalSearch(request: request)
    } else {
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query
        request.resultTypes = [.address, .pointOfInterest]
        if let region = region { request.region = region }
        operation = MKLocalSearch(request: request)
    }
    operation.start { response, error in
        if error != nil { completion(nil, "provider_unavailable"); return }
        // Keep a broader provider set internally so nearest-candidate ranking
        // happens before the public eight-result privacy/context bound.
        completion(Array((response?.mapItems ?? []).prefix(32)), nil)
    }
}

func nearest(_ items: [MKMapItem], to origin: CLLocation) -> [MKMapItem] {
    Array(items.sorted {
        ($0.placemark.location?.distance(from: origin) ?? .greatestFiniteMagnitude) <
        ($1.placemark.location?.distance(from: origin) ?? .greatestFiniteMagnitude)
    }.prefix(8))
}

func isFoodPlace(_ item: MKMapItem, query: String) -> Bool {
    guard normalized(query) == "restaurant",
          let category = item.pointOfInterestCategory?.rawValue.lowercased() else { return false }
    return ["restaurant", "cafe", "bakery", "brewery", "nightlife", "winery", "foodmarket"]
        .contains { category.contains($0) }
}

func resolve(_ query: String, completion: @escaping (MKMapItem?, [[String: Any]]?, String?) -> Void) {
    search(query) { items, error in
        guard let items = items else { completion(nil, nil, error); return }
        if items.isEmpty { completion(nil, [], "no_result"); return }
        let exact = items.filter { normalized($0.name ?? "") == normalized(query) }
        if exact.count == 1 { completion(exact[0], nil, nil); return }
        if exact.count > 1 { completion(nil, exact.prefix(5).map { candidate($0) }, "ambiguous"); return }
        if items.count == 1 { completion(items[0], nil, nil); return }
        completion(nil, items.prefix(5).map { candidate($0) }, "ambiguous")
    }
}

func transport(_ value: String) -> MKDirectionsTransportType? {
    switch value {
    case "driving": return .automobile
    case "walking": return .walking
    case "transit": return .transit
    case "cycling": return .cycling
    default: return nil
    }
}

func launchMode(_ value: String) -> String? {
    switch value {
    case "driving": return MKLaunchOptionsDirectionsModeDriving
    case "walking": return MKLaunchOptionsDirectionsModeWalking
    case "transit": return MKLaunchOptionsDirectionsModeTransit
    case "cycling": return MKLaunchOptionsDirectionsModeCycling
    default: return nil
    }
}

final class OneLocation: NSObject, CLLocationManagerDelegate {
    let manager = CLLocationManager()
    let query: String
    var requested = false
    init(query: String) { self.query = query }
    func begin() {
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
        locationManagerDidChangeAuthorization(manager)
    }
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.authorizationStatus {
        case .notDetermined:
            app.activate(ignoringOtherApps: true)
            manager.requestWhenInUseAuthorization()
        case .authorizedAlways, .authorizedWhenInUse:
            if !requested { requested = true; manager.startUpdatingLocation() }
        default: finish(["error": "permission_denied"])
        }
    }
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let fix = locations.last, fix.horizontalAccuracy >= 0,
              fix.timestamp.timeIntervalSinceNow > -120 else { return }
        manager.stopUpdatingLocation()
        let region = MKCoordinateRegion(center: fix.coordinate,
            latitudinalMeters: 15_000, longitudinalMeters: 15_000)
        search(query, region: region) { items, error in
            if let error = error { finish(["error": error]) }
            finish(["results": nearest(items ?? [], to: fix).map { candidate($0, origin: fix) },
                    "provider": "Apple MapKit"])
        }
    }
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        if (error as? CLError)?.code != .locationUnknown { finish(["error": "location_failed"]) }
    }
}

guard let line = readLine(), let raw = line.data(using: .utf8),
      let input = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
      let action = input["action"] as? String else { finish(["error": "invalid_request"]) }

var locationDelegate: OneLocation?
switch action {
case "search":
    guard let query = input["query"] as? String, let near = input["near"] as? Bool else {
        finish(["error": "invalid_request"])
    }
    if near {
        locationDelegate = OneLocation(query: query)
        locationDelegate!.begin()
    } else {
        search(query) { items, error in
            if let error = error { finish(["error": error]) }
            finish(["results": (items ?? []).prefix(8).map { candidate($0) }, "provider": "Apple MapKit"])
        }
    }
case "search_around":
    guard let query = input["query"] as? String, let center = input["center"] as? String else {
        finish(["error": "invalid_request"])
    }
    resolve(center) { centerItem, choices, error in
        guard let centerItem = centerItem, let location = centerItem.placemark.location else {
            finish(["error": error ?? "destination_unresolved", "candidates": choices ?? []])
        }
        let region = MKCoordinateRegion(center: location.coordinate,
            latitudinalMeters: 15_000, longitudinalMeters: 15_000)
        search(query, region: region) { items, searchError in
            if let searchError = searchError { finish(["error": searchError]) }
            var grounded = items ?? []
            // If the explicitly supplied event location resolves to a food
            // place, it is itself a grounded zero-distance candidate.
            if isFoodPlace(centerItem, query: query) {
                grounded.removeAll { $0.identifier == centerItem.identifier }
                grounded.append(centerItem)
            }
            finish(["results": nearest(grounded, to: location).map { candidate($0, origin: location) },
                    "provider": "Apple MapKit"])
        }
    }
case "route", "open_route":
    guard let origin = input["origin"] as? String,
          let destination = input["destination"] as? String,
          let modeName = input["mode"] as? String,
          let mode = transport(modeName), let openMode = launchMode(modeName) else {
        finish(["error": "unsupported_mode"])
    }
    resolve(destination) { destinationItem, choices, error in
        guard let destinationItem = destinationItem else {
            finish(["error": error ?? "destination_unresolved", "candidates": choices ?? []])
        }
        func proceed(_ source: MKMapItem) {
            if action == "open_route" {
                MKMapItem.openMaps(with: [source, destinationItem],
                    launchOptions: [MKLaunchOptionsDirectionsModeKey: openMode]) { success in
                    finish(success ? ["opened": true, "destination": candidate(destinationItem), "mode": modeName] : ["error": "open_failed"])
                }
                return
            }
            let request = MKDirections.Request()
            request.source = source
            request.destination = destinationItem
            request.transportType = mode
            request.departureDate = Date()
            MKDirections(request: request).calculateETA { response, routeError in
                guard let response = response, routeError == nil else { finish(["error": "route_unavailable"]) }
                finish(["origin": origin == "current location" ? "current location" : candidate(source),
                        "destination": candidate(destinationItem), "mode": modeName,
                        "distance_meters": response.distance,
                        "expected_travel_seconds": response.expectedTravelTime,
                        "as_of": ISO8601DateFormatter().string(from: Date()),
                        "provider": "Apple MapKit"])
            }
        }
        if origin == "current location" { proceed(MKMapItem.forCurrentLocation()) }
        else {
            resolve(origin) { source, sourceChoices, sourceError in
                guard let source = source else {
                    finish(["error": sourceError ?? "origin_unresolved", "candidates": sourceChoices ?? []])
                }
                proceed(source)
            }
        }
    }
default: finish(["error": "unknown_action"])
}

DispatchQueue.main.asyncAfter(deadline: .now() + 15) { finish(["error": "timeout"]) }
app.run()
