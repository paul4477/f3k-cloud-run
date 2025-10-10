import os
import time
#import functions_framework
#import yaml

from flask import Flask

app = Flask(__name__)

from f3k_cl_competition import Round, Group, make_rounds


import json
data = json.load(open('data/test_data.json'))
rounds = make_rounds(data)

def custom_json(obj):
    if isinstance(obj, Round):
        return {'round_number': obj.round_number, 'groups': obj.groups}
    if isinstance(obj, Group):
        return {'group_letter': obj.group_letter, 'sections': obj.sections}
    if isinstance(obj, Section):
        return {'section_type': obj.__class.__name__, 'section_time': obj.sectionTime}
    raise TypeError(f'Cannot serialize object of {type(obj)}')


@app.route("/")
def hello_world():
    """Example Hello World route."""
    #ame = os.environ.get("NAME", "World")
    out = {}
    for r in rounds:
        for g in r:
            for s in g.sections:
                out[s.get_serial_code()] = s.get_description()
    return json.dumps({'data': rounds, 'o': out}, default=custom_json)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
