import os, sys, json, pandas
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from webapp.utils import progressCallback, resetProgress
from webapp.graph import processdata
from webapp.elastic import search_cache

import core.utils.entity_type as ent
from core.search.parse_academic_search import parse_search_results
from core.search.academic_search import *
from core.flower.draw_flower_test import draw_flower
from core.flower.flower_bloomer import getFlower, getPreFlowerData
from core.utils.mkAff import getAuthor, getJournal, getConf, getAff, getConfPID, getJourPID, getConfPID, getAffPID
from core.search.mag_flower_bloom import *
from core.utils.get_entity import entity_from_name
from core.search.influence_df import get_filtered_score
from core.search.search import search_name
from graph.save_cache import saveNewAuthorCache
from core.flower.high_level_get_flower import get_flower_data_high_level, gen_flower_data

# Imports for submit
from core.search.query_paper   import paper_query
from core.search.query_info    import paper_info_check_query, paper_info_mag_check_multiquery
from core.score.agg_paper_info import score_paper_info_list

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
	{"id":"institution", "name":"Institution"},
    {"id":"paper", "name": "Paper"}]


str_to_ent = {
	"author": ent.Entity_type.AUTH,
	"conference": ent.Entity_type.CONF,
	"journal": ent.Entity_type.JOUR,
	"institution": ent.Entity_type.AFFI
    }


# flower_types
flower_leaves = { 'author': [ent.Entity_type.AUTH]
                , 'conf': [ent.Entity_type.CONF, ent.Entity_type.JOUR]
                , 'inst': [ent.Entity_type.AFFI]
                }

def printDict(d):
    for k,v in d.items():
        print('k: {}\tv: {}'.format(k,v))


def loadList(entity):
    path = os.path.join(BASE_DIR, "webapp/cache/"+entity+"List.txt")
    if entity == 'paper':
        return []
    elif entity not in autoCompleteLists.keys():
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

def get_navbar_option(keyword = "", option = ""):
    return {
        "optionlist": optionlist,
        "selectedKeyword": keyword,
        "selectedOption": [opt for opt in optionlist if opt['id'] == option][0] if option != "" else optionlist[0],
    }


@csrf_exempt
def main(request):
    return render(request, "main.html")

@csrf_exempt
def browse(request):

    browse_list_filename = os.path.join(BASE_DIR, 'webapp/static/browse_lists.json')
    with open(browse_list_filename, 'r') as fp:
        browse_list = json.load(fp)

    for entity in browse_list:
        res = search_cache(entity["cache_index"], entity["cache_type"])
        entity["names"] = list(set([n["_source"]["DisplayName"] for n in res]))
        entity["entities"] = [n["_source"] for n in res]
        for e in (entity["entities"]):
            if "Keywords" in e:
                e["Keywords"] = ", ".join(e["Keywords"])
            if "AuthorIds" in e:
                e["AuthorIds"] = json.dumps(e["AuthorIds"])

    data = {
        'list': browse_list,
        "navbarOption": get_navbar_option()
    }

    return render(request, "browse.html", data)


@csrf_exempt
def create(request):
    print(request)

    try:
        data = json.loads(request.POST.get('data'))
        keyword = data.get('keyword', '')
        search = data.get('search') == 'true'
        option = data.get('option')
    except:
        keyword = ""
        option = ""
        search = False

    print(search)
    # render page with data
    return render(request, "create.html", {
        "navbarOption": get_navbar_option(keyword, option),
        "search": search
    })

s = {
    'author': ('<h5>{name}</h5><p>{affiliation}, Papers: {paperCount}, Citations: {citations}</p></div>'),
         # '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {paperCount}</p></div>'
         # '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {citations}</p></div>'),
    'conference': ('<h5>{name}</h5>'
        '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {paperCount}</p></div>'
        '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {citations}</p></div>'),
    'institution': ('<h5>{name}</h5>'
        '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {paperCount}</p></div>'
        '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {citations}</p></div>'),
    'journal': ('<h5>{name}</h5>'
        '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {paperCount}</p></div>'
        '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {citations}</p></div>'),
    'paper': ('<h5>{title}</h5>'
        '<div><p>Citations: {citations}</p></div>')
}

@csrf_exempt
def search(request):
    keyword = request.POST.get("keyword")
    entityType = request.POST.get("option")
    data = get_entities_from_search(keyword, entityType)

    for i in range(len(data)):
        # print(entity)
        entity = {'data': data[i]}
        entity['display-info'] = s[entityType].format(**entity['data'])
        entity['table-id'] = "{}_{}".format(entity['data']['entity-type'], entity['data']['eid'])
        data[i] = entity
        # print(entity)
    print(data[0])
    return JsonResponse({'entities': data}, safe=False)


'''
s = {
    'author': ('<h5>{DisplayName}</h5><p>Papers: {PaperCount}, Citations: {CitationCount}</p></div>'),
         # '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {paperCount}</p></div>'
         # '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {citations}</p></div>'),
    'conference': ('<h5>{DisplayName}</h5>'
        '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {PaperCount}</p></div>'
        '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {CitationCount}</p></div>'),
    'institution': ('<h5>{DisplayName}</h5>'
        '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {PaperCount}</p></div>'
        '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {CitationCount}</p></div>'),
    'journal': ('<h5>{DisplayName}</h5>'
        '<div style="float: left; width: 50%; padding: 0;"><p>Papers: {PaperCount}</p></div>'
        '<div style="float: right; width: 50%; text-align: right; padding: 0;"<p>Citations: {CitationCount}</p></div>'),
    'paper': ('<h5>{PaperTitle}</h5>'
        '<div><p>Citations: {CitationCount}</p></div>')
}

idkeys = {'paper': 'PaperId', 'author': 'AuthorId', 'institution': 'AffiliationId', 'journal': 'JournalId', 'conference': 'ConferenceSeriesId'}

@csrf_exempt
def search(request):
    global idkeys
    keyword = request.POST.get("keyword")
    entity_type = request.POST.get("option")
    data = search_name(keyword, entity_type)
    idkey = idkeys[entity_type]
    for i in range(len(data)):
        # print(entity)
        entity = {'data': data[i]}
        entity['display-info'] = s[entity_type].format(**entity['data'])
        entity['table-id'] = "{}_{}".format(entity_type, entity['data'][idkey])
        data[i] = entity
        # print(entity)
    print(data[0])
    return JsonResponse({'entities': data}, safe=False)
'''

@csrf_exempt
def manualcache(request):
    print(request.POST.get('type'))
    data = (json.loads(request.POST.get('ent_data')))
    print(request)
    print(request.POST)
    print((data))
    if 'Keywords' in data:
        for i, keyword in enumerate(data['Keywords']):
            data['Keywords'][i] = keyword.strip()
    saveNewAuthorCache(data)
#    with open('/localdata3/common/elastic_cache_test.json', 'r') as fh:
#        cache = json.load(fh)
#    with open('/localdata3/common/elastic_cache_test.json', 'w') as fh:
#        cache.append(data)
#        json.dump(cache, fh)

    return JsonResponse({},safe=False)

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
        "navbarOption": get_navbar_option(name, option),
    }

    return render(request, 'view_papers.html', data)


@csrf_exempt
def submit(request):

    data = json.loads(request.POST.get('data'))

    option = data.get("option")
    keyword = data.get('keyword')
    selfcite = data.get("selfcite")
    min_year = int(data.get("bot_year_min"))
    max_year = int(data.get("top_year_max"))

    selection = data.get("selection")
    entity_data = data.get("entity_data")
    print("submit")

    time_cur = datetime.now()

    # Get the selected paper
    selected_papers = list()
    entity_names    = list()
    for eid, row in entity_data.items():
        entity_names.append(row['name'])
        selected_papers = list(map(lambda x : x['eid'], selection[eid]))

    print()
    print('Number of Papers Found: ', len(selected_papers))
    print('Time taken: ', datetime.now() - time_cur)
    print()

    time_cur = datetime.now()

    # Turn selected paper into information dictionary list
    paper_information = paper_info_mag_check_multiquery(selected_papers) # API
    #for paper in selected_papers:
    #    paper_info = paper_info_check_query(paper)
    #    if paper_info:
    #        paper_information.append(paper_info)

    print()
    print('Number of Paper Information Found: ', len(paper_information))
    print('Time taken: ', datetime.now() - time_cur)
    print()

    # Get min and maximum year
    years = [info['Year'] for info in paper_information if 'Year' in info]
    min_year = min(years)
    max_year = max(years) 

    # Normalised entity names
    entity_names = list(set(entity_names))
    normal_names = list(map(lambda x: x.lower(), entity_names))

    # Generate score for each type of flower
    cache         = [None, None, None]
    entity_scores = [None, None, None]
    for i, flower_item in enumerate(flower_leaves.items()):
        name, leaves = flower_item

        # Timer
        time_cur = datetime.now()

        entity_score = score_paper_info_list(paper_information, leaves)
        entity_score = entity_score[~entity_score['entity_id'].str.lower().isin(
                                          normal_names)]
        entity_scores[i] = entity_score
        cache[i] = entity_score.to_json(orient = 'index')

        print()
        print('Scored for', leaves)
        print('Time taken: ', datetime.now() - time_cur)
        print()

    flower_name = '-'.join(entity_names)
    data1, data2, data3 = gen_flower_data(entity_scores,
                                          flower_name)

    data = {
        "author": data1,
        "conf": data2,
        "inst": data3,
        "yearSlider": {
            "title": "Publications range",
            "range": [min_year, max_year] # placeholder value, just for testing
        },
        "navbarOption": get_navbar_option(keyword, option)
    }

    request.session['cache'] = cache
    request.session['name']  = flower_name
    return render(request, "flower.html", data)



@csrf_exempt
def submit_from_browse(request):

    data = json.loads(request.POST.get('data'))

    option = data.get("option")
    keyword = data.get('keyword')
    authorids = data.get('AuthorIds')
    normalizedname = data.get('NormalizedName')

    selection = data.get("selection")
    print('\n\n\n\n\n{}\n\n\n\n\n\n'.format(selection))
    entity_data = data.get("entity_data")
    print("submit")

    # Default Dates need fixing
    min_year = None
    max_year = None

    cache, data = get_flower_data_high_level(option, authorids, normalizedname)
    data["navbarOption"] = get_navbar_option(keyword, option)

    request.session['cache'] = cache
    request.session['name']  = normalizedname
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

    cache  = request.session['cache']
    scores = [pd.read_json(c, orient = 'index') for c in cache]
    name   = request.session['name']
    data1, data2, data3 = gen_flower_data(scores,
                                          name,
                                          min_year = from_year,
                                          max_year = to_year)

    data = {
        "author": data1,
        "conf": data2,
        "inst": data3,
        "navbarOption": get_navbar_option(keyword, option)
    }
    return JsonResponse(data, safe=False)
