"""Replaceable, fixed-endpoint structured forecast reader. No model or scraping."""
import json
import math
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from zoneinfo import ZoneInfo
from configuration import home
from security_policy import enforced


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Unexpected weather redirect')


def location():
    path=home() / 'config/weather.json'
    data = json.loads(path.read_text()) if path.exists() else {'mode':'current'}
    if data == {'mode':'current'}:
        from weather_location import current
        data=current()
    if set(data) != {'latitude', 'longitude', 'label'}:
        raise ValueError('Invalid weather configuration')
    for key, limit in [('latitude',90),('longitude',180)]:
        if type(data[key]) not in (float,int) or not math.isfinite(data[key]) or abs(data[key]) > limit:
            raise ValueError('Invalid coordinate')
    if not isinstance(data['label'],str) or not 1 <= len(data['label']) <= 80:
        raise ValueError('Invalid location label')
    return data


def number(value, low, high):
    if type(value) not in (float,int) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Missing or invalid forecast number')
    return value


def normalize(data):
    zone = ZoneInfo(data['timezone'])
    now = datetime.now(zone)
    current = data['current']
    stamp = datetime.fromisoformat(current['time']).replace(tzinfo=zone)
    if abs((now-stamp).total_seconds()) > 7200:
        raise ValueError('Stale weather')
    result = {'source':'Open-Meteo', 'url':'https://open-meteo.com/',
              'timezone':data['timezone'], 'as_of':stamp.isoformat(),
              'current':{'temperature':number(current['temperature_2m'],-150,160),
                         'code':number(current['weather_code'],0,99)}, 'hours':[]}
    hourly=data['hourly']
    for i,t in enumerate(hourly['time'][:72]):
        hour=datetime.fromisoformat(t).replace(tzinfo=zone)
        result['hours'].append({'time':hour.isoformat(),
            'temperature':number(hourly['temperature_2m'][i],-150,160),
            'rain':number(hourly['precipitation_probability'][i],0,100),
            'wind':number(hourly['wind_speed_10m'][i],0,300),
            'code':number(hourly['weather_code'][i],0,99)})
    if not result['hours']:
        raise ValueError('Empty forecast')
    return result


@enforced('get_weather')
def get_weather():
    try:
        loc=location()
    except (OSError,ValueError,TypeError):
        return {'error':'I could not get a current location for weather. Please try again shortly.'}
    try:
        query=urllib.parse.urlencode({'latitude':loc['latitude'],'longitude':loc['longitude'],
            'current':'temperature_2m,weather_code',
            'hourly':'temperature_2m,precipitation_probability,wind_speed_10m,weather_code',
            'temperature_unit':'fahrenheit','wind_speed_unit':'mph','timezone':'auto','forecast_days':3})
        import certifi  # Already locked transitively; same trust bundle as asset setup.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
        with opener.open('https://api.open-meteo.com/v1/forecast?'+query,timeout=5) as response:
            raw=response.read(100001)
        if len(raw)>100000:
            raise ValueError('Oversized forecast')
        return normalize(json.loads(raw))
    except Exception:
        return {'error':'Current weather is unavailable. Please try again later.'}
