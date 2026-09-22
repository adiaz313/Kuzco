"""Bounded pre-model Skills for the production direct + resident 8B policy.

Only complete user requests match. History follow-ups require a previously
completed weather turn; tool and assistant text never become action authority.
"""
import json
import re
import time
import logging
from . import greeting,greeting_context,timekeeping,weather,reminders,mac_control,calendar_readonly,calendar_skill,maps_places,travel_time,recommendations


def clean(prompt):
    text=' '.join(prompt.lower().replace('’',"'").split()).strip(' .!?')
    # Whisper can spell the address differently. Remove addresses only at edges,
    # never words from the user's substantive request.
    name=r'(?:kuzco|cuzco|cusco|kusco|kuzko)'
    text=re.sub(r'^(?:hey\s+)?'+name+r'[\s,.!?—:-]+','',text)
    text=re.sub(r'^(?:please )','',text)
    return re.sub(r'(?:,? please|[,\s.!?]+(?:'+name+r'))$','',text).strip(' .!?')


def previous_weather(history):
    if not history:return None
    # Only metadata emitted by this Skill is used. It contains enums, not evidence.
    for message in history[-1]:
        if message.get('role')=='assistant':
            try:
                value=json.loads(message['content']).get('weather_intent')
                if isinstance(value,list) and len(value)==2 and value[0] in {'current','forecast','high','low','rain','umbrella','jacket','grill'} and value[1] in {'today','tonight','tomorrow'}:
                    return ('forecast' if value[0]=='current' else value[0],value[1])
            except (ValueError,TypeError,AttributeError):pass
    return None


def handle(prompt, history, personality, execute, debug_print, debug):
    started=time.perf_counter()
    reminder = reminders.handle(prompt, history, personality, execute, debug_print, debug)
    if reminder is not None:
        return reminder
    control = mac_control.handle(prompt, history, personality, execute, debug_print, debug)
    if control is not None:
        return control
    calendar = calendar_readonly.handle(prompt, history, personality, execute, debug_print, debug)
    if calendar is not None:
        return calendar
    schedule = calendar_skill.handle(prompt, history, personality, execute, debug_print, debug)
    if schedule is not None:
        return schedule
    travel = travel_time.handle(prompt, history, personality, execute, debug_print, debug)
    if travel is not None:
        return travel
    recommendation = recommendations.handle(prompt, history, personality, execute, debug_print, debug)
    if recommendation is not None:
        return recommendation
    places = maps_places.handle(prompt, history, personality, execute, debug_print, debug)
    if places is not None:
        return places
    text=clean(prompt)
    clock=timekeeping.parse(text)
    forecast=weather.parse(text,previous_weather(history))
    social=greeting.matches(text)
    if not (clock or forecast or social):
        if re.search(r'\b(?:time|clock)\b',text):
            logging.getLogger('kuzco.background').info('Clock wording unmatched; model fallback (request content omitted)')
        if re.search(r'\b(?:grill|grilling|jacket|umbrella|weather)\b',text):
            logging.getLogger('kuzco.background').info('Weather intent unmatched; general fallback (request content omitted)')
        return None
    selected='timekeeping' if clock else 'weather' if forecast else 'greeting'
    logging.getLogger('kuzco.background').info('Direct skill=%s',selected)
    if forecast:
        logging.getLogger('kuzco.background').info('Weather route intent=%s period=%s',*forecast)
    route_s=time.perf_counter()-started
    turn=[{'role':'user','content':prompt}]
    result=None
    if social:
        previous=None
        if history:
            try:previous=json.loads(history[-1][-1]['content']).get('answer')
            except (ValueError,KeyError,TypeError):pass
        observation=greeting_context.gather(execute)
        answer=greeting.respond(personality,previous,greeting_context.daypart(),observation)
    else:
        tool='get_current_time' if clock else 'get_weather'
        call={'tool':tool,'arguments':{}}
        turn.append({'role':'assistant','content':json.dumps(call)})
        result=execute({'function':{'name':tool,'arguments':'{}'}},())
        answer=timekeeping.respond(clock,result,personality) if clock else weather.respond(forecast,result,personality)
        # Retain source/time and the interpreted evidence, not three days of hourly arrays.
        evidence=result if clock or result.get('error') else {key:result[key] for key in ('source','url','timezone','as_of','current')}
        if forecast and not result.get('error'):
            evidence=dict(evidence, interpretation=answer, period=forecast[1])
        turn.append({'role':'user','content':json.dumps({'tool':tool,'tool_result':evidence,'tool_call_id':'call_1'})})
    final={'answer':answer}
    if forecast:final['weather_intent']=forecast
    turn.append({'role':'assistant','content':json.dumps(final)})
    history.append(turn)
    metrics={'effective':selected.upper(),'routing_s':route_s,'total_s':time.perf_counter()-started,'llm_calls':0}
    debug_print(debug,'Selected Skill',selected)
    debug_print(debug,'skill timing',metrics)
    if result is not None:debug_print(debug,'raw tool result',result)
    debug_print(debug,'final answer',answer)
    return answer,metrics
