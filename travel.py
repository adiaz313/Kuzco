"""Trusted read-only composition of EventKit and MapKit travel evidence."""
from datetime import datetime, timedelta

from security_policy import enforced


@enforced('travel_route')
def route(destination, calendar_selector, mode):
    if mode not in {'driving', 'walking', 'transit', 'cycling'}:
        return {'error': 'unsupported_mode'}
    if bool(destination) == bool(calendar_selector):
        return {'error': 'invalid_request'}
    event_start = None
    if calendar_selector:
        import calendar_read
        now = datetime.now().astimezone()
        result = calendar_read._invoke('range', start_iso=now.isoformat(timespec='seconds'),
            end_iso=(now + timedelta(days=30)).isoformat(timespec='seconds'), timed_only=True,
            include_location=True)
        if result.get('error'):
            return {'error': 'calendar_unavailable'}
        events = []
        selector = calendar_selector.removesuffix(' appointment').strip()
        for event in result.get('events', []):
            try:
                start, end = datetime.fromisoformat(event['start_iso']), datetime.fromisoformat(event['end_iso'])
            except (KeyError, TypeError, ValueError):
                continue
            if end <= now or event.get('all_day'):
                continue
            if calendar_selector == 'next appointment' or selector in event.get('title', '').lower():
                events.append((start, event))
        events.sort(key=lambda pair: pair[0])
        if not events:
            return {'error': 'calendar_event_missing'}
        if calendar_selector != 'next appointment' and len(events) > 1:
            return {'error': 'calendar_event_ambiguous'}
        event_start, event = events[0]
        location = event.get('location')
        if not isinstance(location, str) or not location.strip() or len(location) > 500:
            return {'error': 'calendar_location_missing'}
        destination = location.strip()
    import maps_places
    result = maps_places._invoke('route', origin='current location', destination=destination, mode=mode)
    if event_start is not None and not result.get('error'):
        result = dict(result, event_start_iso=event_start.isoformat(), calendar_event=True)
    return result
