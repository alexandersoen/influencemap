import os, sys, json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from .utils import progressCallback, resetProgress
from .graph import processdata


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIR = os.path.join(os.path.dirname(BASE_DIR), 'python')
sys.path.insert(0, PYTHON_DIR)

import entity_type as ent
from mkAff import getAuthor, getJournal, getConf, getAff, getConfPID, getJourPID, getConfPID, getAffPID
from mag_flower_bloom import *

#import entity_type as ent
#from academic_search import get_search_results
#from flower_bloom_data import score_dict_to_graph
#from draw_flower_test import draw_flower
#from flower_bloomer import getFlower, getPreFlowerData
#from mkAff import getAuthor, getJournal, getConf, getAff, getConfPID, getJourPID, getConfPID, getAffPID
# initialise as no saved pids
saved_pids = dict()

# initialise as no saved entities
saved_entities = dict()

# initialise as no expanded ids
expanded_ids = dict()

# initialise no stored flower data frames
pre_flower_data_dict = dict()

# initialise as no autocomplete lists yet (wait until needed)
autoCompleteLists = {}

# dictionary to store option specific functions
dataFunctionDict = {
    'get_ids':{
	'author': getAuthor,
	'conference': getConf,
	'institution': getAff,
	'journal': getJournal},
    'get_pids':{
	'conference': getConfPID,
	'journal': getJourPID,
	'institution': getAffPID}}

# option list for radios
optionlist = [  # option list
	{"id":"author", "name":"Author"},
	{"id":"conference", "name":"Conference"},
	{"id":"journal", "name":"Journal"},
	{"id":"institution", "name":"Institution"}]


def printDict(d):
    for k,v in d.items():
        print('k: {}\tv: {}'.format(k,v))


def loadList(entity):
    path = os.path.join(BASE_DIR, "webapp/cache/"+entity+"List.txt")
    if entity not in autoCompleteLists.keys():
        with open(path, "r") as f:
            autoCompleteLists[entity] = [name.strip() for name in f]
        autoCompleteLists[entity] = list(set(autoCompleteLists[entity]))
    return autoCompleteLists[entity]

def autocomplete(request):
    entity_type = request.GET.get('option')
    data = loadList(entity_type)
    return JsonResponse(data,safe=False)

selfcite = False
expanded_ids = dict()

@csrf_exempt
def main(request):
    return render(request, "main.html")

@csrf_exempt
def create(request):
    print(request)
 
    try:
        data = json.loads(request.POST.get('data'))
        keyword = data.get('keyword', '')
        search = data.get('search') == 'true'
        option = [opt for opt in optionlist if opt['id'] == data.get('option')][0]
    except:
        keyword = ""
        search = False
        option = optionlist[0] # default selection
    print(search)    
    # render page with data
    return render(request, "create.html", {
	"navbarOption": {
	    "optionlist": optionlist,
	    "selectedKeyword": keyword,
	    "selectedOption": option,
	},
        "search": search
    })


@csrf_exempt
def search(request):
    keyword = request.POST.get("keyword")
    data = get_search_results(keyword)

    author_key_change = [
      ['eid', 'Id'],
      ['normalisedName', 'AuN'],
      ['name', 'DAuN'],
      ['citations', 'CC'],
      ['affiliation', 'E', 'LKA', 'AfN'],
      ['affiliationid', 'E', 'LKA', 'AfId']
    ]

    author_keys_to_make_dictionaries = [
        ['E']
    ]

    def get_nested_value(dictionary, keys, rtn_func=lambda x: x):
        if keys == []:
            return rtn_func(dictionary)
        else:
            return get_nested_value(dictionary[keys[0]], keys[1:], rtn_func)

    def result_to_dictionary(result, key_change, keys_to_make_dictionaries):
        out = dict()
        for keys in keys_to_make_dictionaries:
            result[keys[-1]] = get_nested_value(result, keys, json.loads)

        for elem in key_change:
            try:
                out[elem[0]] = get_nested_value(result, elem[1:])
            except:
                #out[elem[0]] = get_nested_value(result, elem[1:])
                out[elem[0]] = None
        return out

    data = [result_to_dictionary(entity, author_key_change, author_keys_to_make_dictionaries) for entity in data["entities"]]

    return JsonResponse({'entities': data}, safe=False)


def view_papers(request):
    print(request)
    resetProgress()
    data = json.loads(request.POST.get('data'))
    selectedIds = data.get('selectedIds').split(',')
    selectedNames = data.get('selectedNames').split(',')
    entityType = data.get('entityType')
    expanded = data.get('expanded') 
    option = data.get('option')
    name = data.get('name')
    if entityType == 'author':
        entities = saved_entities[name]
        paper_dict = saved_pids[name]
        entities = [x for x in entities if x['id'] in selectedIds]
        for entity in entities:
            entity['field'] = ['_'.join([str(y) for y in x]) for x in entity['field']]
    else:
        entities = saved_entities[name]
        get_pid_params = [selectedIds] if entityType != 'institution' else ([{'id':selectedIds[i],'name':selectedNames[i]} for i in range(len(selectedIds))], name)
        paper_dict = dataFunctionDict['get_pids'][entityType](*get_pid_params)
        entities = [x for x in entities if x['id'] in selectedIds]

    simplified_paper_dict = dict()

    for k, v in paper_dict.items(): # based on a dict of type entity(aID, entity_type('auth_id')):[(paperID, affiliationName, paperTitle, year, date, confName)] according to mkAff.py
        eid = k.entity_id
        if eid in selectedIds:
            sorted_papers = sorted(v, key= lambda x: x['year'] if entityType != 'institution' else x['paperID'], reverse = True)
            simplified_paper_dict[eid] = sorted_papers
    data = {
        'entityTuples': entities,
        'papersDict': simplified_paper_dict,
        'entityType': entityType,
        'selectedInfo': selectedIds,
        'keyword': name,
        "navbarOption": {
            "optionlist": optionlist,
            "selectedKeyword": name,
            "selectedOption": [opt for opt in optionlist if opt['id'] == option][0],
        }

    }

    return render(request, 'view_papers.html', data)



@csrf_exempt
def submit(request):

    # print(request)
    # resetProgress()
    # global saved_pids
    data = json.loads(request.POST.get('data'))
    # papers_string = data['papers']   # 'eid1:pid,pid,...,pid_entity_eid2:pid,...'
    # id_papers_strings = papers_string.split('_entity_')
    # id_2_paper_id = dict()

    # for id_papers_string in id_papers_strings:
    #     eid, pids = id_papers_string.split(':')
    #     id_2_paper_id[eid] = pids.split(',')

    # unselected_papers_string = data.get('unselected_papers')   # 'eid1:pid,pid,...,pid_entity_eid2:pid,...'
    # unselected_id_papers_strings = unselected_papers_string.split('_entity_')

    # unselected_id_2_paper_id = dict()
    # if unselected_papers_string != "":
    #     for us_id_papers_string in unselected_id_papers_strings:
    #         us_eid, us_pids = us_id_papers_string.split(':')
    #         unselected_id_2_paper_id[us_eid] = us_pids.split(',')


    option = data.get("option")
    keyword = data.get('keyword')
    selfcite = data.get("selfcite") 
    bot_year_min = int(data.get("bot_year_min"))
    top_year_max = int(data.get("top_year_max"))

    # pre_flower_data_dict[request.session['id']] = getPreFlowerData(id_2_paper_id, unselected_id_2_paper_id, ent_type = option, cbfunc=progressCallback)
    # flower_data = getFlower(data_df=pre_flower_data_dict[request.session['id']], name=keyword, ent_type=option, cbfunc=progressCallback, inc_self=selfcite)

    entity_score_df = get_entity_score_df(keyword, ent.Entity_type.AUTH) # TODO other entities
    flower_data = get_flowers(entity_score_df, cbfunc=progressCallback, \
        bot_year=bot_year_min, top_year=top_year_max)

    data1 = processdata("author", flower_data[0])
    data2 = processdata("conf", flower_data[1])
    data3 = processdata("inst", flower_data[2])

    # print(data)
    # print(selfcite)

    #data1 = processdata("conf", score_dict_to_graph(keyword, draw_flower(keyword)))


    data = {
        "author": data1,
        "conf": data2,
        "inst": data3,
        "navbarOption": {
            "optionlist": optionlist,
            "selectedKeyword": keyword,
            "selectedOption": option,
        },
        "yearSlider": {
            "title": "Publications range",
            "range": [bot_year_min, top_year_max] # placeholder value, just for testing
        },
        "navbarOption": {
            "optionlist": optionlist,
            "selectedKeyword": keyword,
            "selectedOption": [opt for opt in optionlist if opt['id'] == option][0],
        }

    }
    return render(request, "flower.html", data)

@csrf_exempt
def resubmit(request):
    print(request)
    from_year = int(request.POST.get('from_year'))
    to_year = int(request.POST.get('to_year'))
    option = request.POST.get('option')
    keyword = request.POST.get('keyword')
    pre_flower_data = []
    selfcite = request.POST.get('selfcite') == 'true'

    flower_data = getFlower(data_df=pre_flower_data_dict[request.session['id']], name=keyword, ent_type=option, bot_year=from_year, top_year=to_year, inc_self=selfcite)

    data1 = processdata("author", flower_data[0])
    data2 = processdata("conf", flower_data[1])
    data3 = processdata("inst", flower_data[2])

    data = {
        "author": data1,
        "conf": data2,
        "inst": data3,
        "navbarOption": {
            "optionlist": optionlist,
            "selectedKeyword": keyword,
            "selectedOption": option,
        },
    }
    return JsonResponse(data, safe=False)

