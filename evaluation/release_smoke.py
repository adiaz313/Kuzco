"""Explicit bounded local smoke check. Uses synthetic memory/documents only.

Run from the repository root with a fresh KUZCO_HOME. Opens Calculator and
queries public web evidence; never invoked by startup or ordinary tests.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import ROOT
from routed import RoutingAgent


def main():
    agent=RoutingAgent('direct')
    history=[]
    rows=[]
    tasks=[('time','What time is it?',()),
           ('application','Open Calculator.',()),
           ('memory','What do you remember about release validation?',()),
           ('documents','What was the Northwind product idea?',(ROOT/'examples/notes.txt',)),
           ('web','Who is the governor of Michigan?',()),
           ('conversation','Reply with a brief acknowledgment that you are available.',())]
    for label,prompt,documents in tasks:
        start=time.perf_counter()
        try:
            answer=agent(prompt,documents,history=history,personality='kuzco')
            row={'case':label,'seconds':round(time.perf_counter()-start,3),'answer':answer}
        except Exception as error:
            row={'case':label,'seconds':round(time.perf_counter()-start,3),'error':type(error).__name__}
        rows.append(row)
        print(json.dumps(row),flush=True)
    return rows


if __name__ == '__main__':
    main()
