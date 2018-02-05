import os, sys, json
import numpy as np
from operator import itemgetter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIR = os.path.join(os.path.dirname(BASE_DIR), 'python')
sys.path.insert(0, PYTHON_DIR)

def processdata(gtype, egoG):
    center_node = egoG.graph['ego']

    # Radius of circle
    radius = 1.2

    # Get basic node information from ego graph
    outer_nodes = list(egoG)
    outer_nodes.remove(center_node)
    outer_nodes.sort(key=lambda n : egoG.nodes[n]['ratiow'])

    links = egoG.edges(data=True)
    anglelist = np.linspace(np.pi, 0., num=len(outer_nodes))
    x_pos = [0]; x_pos.extend(list(radius * np.cos(anglelist)))
    y_pos = [0]; y_pos.extend(list(radius * np.sin(anglelist)))

    # Outer nodes data
    nodedata = { key:{
            "name": key,
            "weight": egoG.nodes[key]["nratiow"],
            "id": i,
            "gtype": gtype,
            "size": egoG.nodes[key]["sumw"],
            "xpos": x_pos[i],
            "ypos": y_pos[i],
            "coauthor": str(egoG.nodes[key]['coauthor'])
        } for i, key in zip(range(1, len(outer_nodes)+1), outer_nodes)}

    # Center node data
    nodedata[center_node] = {
        "name": center_node,
        "weight": 1,
        "id": 0,
        "gtype": gtype,
        "size": 1,
        "xpos": x_pos[0],
        "ypos": y_pos[0],
        "coauthor": str(False)
    }

    nodekeys = [v["name"] for v in sorted(nodedata.values(), key=itemgetter("id"))]

    linkdata = [{
            "source": nodekeys.index(s),
            "target": nodekeys.index(t),
            "padding": nodedata[t]["size"],
            "id": nodedata[t]["id"] if v["direction"] == "in" else nodedata[s]["id"],
            "gtype": gtype,
            "type": v["direction"],
            "weight": v["nweight"]
        } for s, t, v in links]

    chartdata = [{
            "id": nodedata[t]["id"] if v["direction"] == "in" else nodedata[s]["id"],
            "name": t if v["direction"] == "in" else s,
            "type": v["direction"],
            "gtype": gtype,
            "sum": nodedata[t]["weight"] if v["direction"] == "in" else nodedata[s]["weight"],
            "weight": v["weight"]
        } for s, t, v in links]
    chartdata = sorted(chartdata, key=itemgetter("sum"))
    return { "nodes": list(nodedata.values()), "links": linkdata, "bars": chartdata }

