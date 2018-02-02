import os, sys, json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from .utils import progressCallback
from .graph import processdata
from urllib import parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIR = os.path.join(os.path.dirname(BASE_DIR), 'python')
sys.path.insert(0, PYTHON_DIR)

from flower_bloomer import getFlower, getPreFlowerData
from mkAff import getAuthor, getJournal, getConf, getAff, getConfPID, getJourPID, getConfPID, getAffPID
# initialise as no saved pids
saved_pids = dict() 

# initialise as no expanded ids
expanded_ids = dict()

# initialise as no autocomplete lists yet (wait until needed)
autoCompleteLists = {}
optionlist = [  # option list
    {"id":"author", "name":"Author"},
    {"id":"conference", "name":"Conference"},
    {"id":"journal", "name":"Journal"},
    {"id":"institution", "name":"Institution"}
]

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
def search(request):

    request.session['id'] = 'id_' + str(datetime.now())

    global saved_pids, expanded_ids
    print("search!!", request.GET)

    entities = []

    keyword = request.GET.get("keyword")
    option = request.GET.get("option")
    expand = True if request.GET.get("expand") == 'true' else False

    if keyword not in expanded_ids.keys():
        expanded_ids[keyword] = list()

    if keyword:
        if option == 'author':
            try:
                entities, saved_pids[keyword], expanded_ids[keyword] = getAuthor(keyword, progressCallback, nonExpandAID=expanded_ids[keyword], expand=expand)
            except:
                entities_and_saved_pids = getAuthor(keyword, progressCallback, nonExpandAID=expanded_ids[keyword], expand=expand)
                entities = entities_and_saved_pids[0]
                saved_pids[keyword] = {**entities_and_saved_pids[1], **saved_pids[keyword]}
        else:
            entities = dataFunctionDict['get_ids'][option](keyword, progressCallback)

    data = {"entities": entities,}
    print('\n\n\n\n\n{}\n\n\n\n\n\n'.format(request.session['id']))
    return JsonResponse(data, safe=False)



def submit(request):
    request.session['id'] = 'id_' + str(datetime.now())
    print('\n\n\n\n\n{}\n\n\n\n\n\n'.format(request.session['id']))
    global option, saved_pids

    papers_string = request.GET.get('papers')   # 'eid1:pid,pid,...,pid_entity_eid2:pid,...'
    id_papers_strings = papers_string.split('_entity_')

    id_2_paper_id = dict()

    for id_papers_string in id_papers_strings:
        eid, pids = id_papers_string.split(':')
        id_2_paper_id[eid] = pids.split(',')

    option = request.GET.get("option")
    keyword = request.GET.get('keyword')
    selfcite = True if request.GET.get("selfcite") == "true" else False
#    print('\n\n\n\n\n\n\n\n{}\n\n\n\n\n\n\n'.format(tid_2_paper_id))

    request.session['pre_flower_data'] = getPreFlowerData(id_2_paper_id)

    flower_data = getFlower(data_df=request.session['pre_flower_data'], name=keyword, ent_type=option)

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
            "selectedOption": [o for o in optionlist if o["id"] == option][0],
        },
        "yearSlider": {
            "title": "Publications range",
            "range": [2000,2014] # placeholder value, just for testing
        }
    }
    return render(request, "flower.html", data)

def resubmit(request):
    from_year = request.GET.get('from_year')
    to_year = request.GET.get('to_year')
    option = request.GET.get('option')
    name = request.GET.get('keyword')
    pre_flower_data = []
    flower_data = getFlower(data_df=request.session['pre_flower_data'], name=keyword, ent_type=option)

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
            "selectedOption": [o for o in optionlist if o["id"] == option][0],
        },
        "yearSlider": {
            "title": "Publications range",
            "range": [2000,2014] # placeholder value, just for testing
        }
    }
    return JsonResponse(data, safe=False)


def printDict(d):
    for k,v in d.items():
        print('k: {}\tv: {}'.format(k,v))


def main(request):
    global keyword, optionlist, option, selfcite
    keyword = ""
    option = optionlist[0] # default selection
    # render page with data
    return render(request, "main.html", {
        "navbarOption": {
            "optionlist": optionlist,
            "selectedKeyword": keyword,
            "selectedOption": option,
        }
    })

def view_papers(request):
    print("\n\nrequest: {}\n\n".format(request))

    selectedIds = request.GET.get('selectedIds').split(',')
    selectedNames = request.GET.get('selectedNames').split(',')
    entityType = request.GET.get('entityType')
    expanded = request.GET.get('expanded') == 'true'
    name = request.GET.get('name')

    if entityType == 'author':
        if expanded:
            entities, paper_dict = getAuthor(name=name, expand=True)
        else:
            entities, paper_dict, _ = getAuthor(name=name, expand=False)
        entities = [x for x in entities if x['id'] in selectedIds]   
        for entity in entities:
            entity['field'] = ['_'.join([str(y) for y in x]) for x in entity['field']]
    else:
        entities = dataFunctionDict['get_ids'][entityType](name)
        get_pid_params = (selectedIds) if entityType != 'institution' else ([{'id':selectedIds[i],'name':selectedNames[i]} for i in range(len(selectedIds))], name)
        paper_dict = dataFunctionDict['get_pids'][entityType](*get_pid_params)
        entities = [x for x in entities if x['id'] in selectedIds]   



    simplified_paper_dict = dict()
    for k, v in paper_dict.items(): # based on a dict of type entity(aID, entity_type('auth_id')):[(paperID, affiliationName, paperTitle, year, date, confName)] according to mkAff.py
        eid = k.entity_id
        sorted_papers = sorted(v, key= lambda x: x[2], reverse = True)
        if eid in selectedIds:
            simplified_paper_dict[eid] = ['_'.join([x[2],x[3],x[0],x[5]]) for x in sorted_papers] # to create a string of title_year_id

    print("simplified_paper_dict: {}".format(simplified_paper_dict))
    print("paper_dict: {}".format(paper_dict))

    data = {
        'entityTuples': entities,
        'papersDict': simplified_paper_dict,
        'entityType': entityType, 
        'selectedInfo': selectedIds,
        'keyword': name
    }

    print('\n\n\n\n\n{}\n\n\n\n\n\n'.format(request.session['id']))
    return render(request, 'view_papers.html', data)
