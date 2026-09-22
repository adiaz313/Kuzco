"""Trusted candidate-first composition for local place recommendations."""
from datetime import datetime, timedelta

from security_policy import enforced


def _event_location(selector):
    import calendar_read
    now = datetime.now().astimezone()
    result = calendar_read._invoke('range', start_iso=now.isoformat(timespec='seconds'),
        end_iso=(now + timedelta(days=30)).isoformat(timespec='seconds'), timed_only=True,
        include_location=True)
    if result.get('error'):
        return None, 'calendar_unavailable'
    events = []
    for event in result.get('events', []):
        try:
            start, end = datetime.fromisoformat(event['start_iso']), datetime.fromisoformat(event['end_iso'])
        except (KeyError, TypeError, ValueError):
            continue
        if end > now and not event.get('all_day'):
            events.append((start, event))
    events.sort(key=lambda item: item[0])
    if not events:
        return None, 'calendar_event_missing'
    location = events[0][1].get('location')
    if not isinstance(location, str) or not location.strip() or len(location) > 200:
        return None, 'calendar_location_missing'
    return location.strip(), None


@enforced('recommend_places')
def recommend_places(query, calendar_selector):
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        return {'error': 'invalid_request'}
    if calendar_selector not in {'', 'next appointment'}:
        return {'error': 'invalid_request'}
    import maps_places
    if calendar_selector:
        center, error = _event_location(calendar_selector)
        if error:
            return {'error': error}
        return maps_places._invoke('search_around', query=query.strip(), center=center)
    return maps_places._invoke('search', query=query.strip(), near=True)

