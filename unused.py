import yaml
import json
from lookerapi import LookerApi
from pprint import pprint
from collections import defaultdict
from collections import Counter
from itertools import groupby
import re
import argparse
import sys

# ------- HERE ARE PARAMETERS TO CONFIGURE -------
# host name in config.yml
host = 'mylooker'
# host = 'cs_eng'
# model that you wish to analyze
# model = ['ML, postgres']
model = ['thelook']
# model = 'calendar, e_commerce'
# projects = ['the_look_fabio']

# How far you wish to look back
timeframe = '90 days'


def main():
    parser = argparse.ArgumentParser()

    # auth arguments
    auth_parser = parser.add_argument_group("Authentication")
    auth_parser.add_argument('--host', type=str, default=host,
                             required=('--client_id' or
                                       '--client_secret') in sys.argv,
                             help='# Looker Host, Default: localhost')
    auth_parser.add_argument('--port', type=int, default=19999,
                             help='# Looker API Port, Default: 19999')
    auth_parser.add_argument('--client_id', type=str,
                             required='--client_secret' in sys.argv,
                             help="# API3 Client Id")
    auth_parser.add_argument('--client_secret', type=str,
                             required='--client_id' in sys.argv,
                             help="# API3 Client Secret")

    subparsers = parser.add_subparsers(title='Subcommands',
                                       dest='command',
                                       description='Valid Subcommands',
                                       help='additional help')
    # subparsers.required = True # works, but might do without for now.

    # parser for ls command
    # -p:
    # -m: can specify one or more models
    # -e: lists all explores
    ls_parser = subparsers.add_parser('ls', help='ls help')
    ls_parser.set_defaults(func=ls)
    ls_parser.add_argument('-p', '--project',
                           type=str,
                           default=False,  # when -p is not called
                           const=None,  # when -p is called w/o arg
                           nargs='?',
                           help='Lists all projects')
    ls_parser.add_argument('-m', '--model',
                           type=str,
                           nargs='+' if '-e' in sys.argv else '*',
                           default=False,
                           const=None,
                           required='-e' in sys.argv,
                           help='Lists all models')
    ls_parser.add_argument('-e', '--explore',
                           action='store_true',
                           help='Lists all explores')

    # parser for fu command
    fu_parser = subparsers.add_parser('fu', help='fu help')

    args = vars(parser.parse_args())  # Namespace object
    auth_params = ('host', 'port', 'client_id', 'client_secret')
    auth_args = {k: args[k] for k in auth_params}

    # authenticate
    looker = authenticate(**auth_args)

    # map subcommand to function
    if args['command'] == 'ls':
        # do ls stuff
        ls_args = {k: args[k] for k in ('project', 'model', 'explore')}
        if (ls_args['project'] is False and ls_args['model'] is False
                and ls_args['explore'] is False):
            parser.error('No action requested. Try ls --help for help')
        else:
            ls(looker, **ls_args)
    elif args['command'] == 'fu':
        # do fu stuff
        print('fu stuff')
    else:
        print('No command passed')

    # pprint(aggregate_usage(looker, None, timeframe, aggregation='model'))
    # pprint(get_field_usage(looker, timeframe, None )['model'])
    # get_explore_fields(looker, model = ['thelook'])


# ls func
# If project flagged was used, call get_projects with list of projects or None.
def ls(looker, **kwargs):
    if kwargs['project'] is not False:
        p = kwargs['project'].split(' ') if kwargs['project'] is not None else None
        r, mc, vc = get_project_files(looker, project=p)
        for idx, i in enumerate(r):
            s = '{} (models: {}, views: {})'.format(i['project'], mc[idx], vc[idx])
            print(s)
    elif kwargs['model'] is not False and kwargs['explore'] is False:
        m = None if len(kwargs['model']) == 0 else kwargs['model']
        pprint(get_models(looker, model=m, scoped_names=1))
    elif kwargs['explore']:
        pprint(get_explores(looker, project=None, model=kwargs['model'], scoped_names=1))
    return


# parses strings for view_name.field_name and returns a list (empty if no matches)
def parse(string):
    return re.findall(r'(\w+\.\w+)', str(string))


# function that returns list of model definitions (verbose=1) or model names
# (verbose=0). Allows the user to specify a project name, a model name or
# nothing at all. project paramater is a string while model parameter is a list
def get_models(looker, project=None, model=None, verbose=0, scoped_names=0):
    if project is None and model is None:
        models = looker.get_models()
    elif project is not None and model is None:
        # if no parameters are specified
        response = looker.get_models()
        models = list(filter(lambda x: x['project_name'] == project, response))
    elif project is not None and model is not None:
        # if both project and model paramaters are specified
        print('''Warning: Project parameter ignored.
              Model names are unique across projects in Looker.''')
        models = [looker.get_model(m) for m in model]
    else:
        # in case project parameter wasn't passed but model was. Behaves as above.
        models = [looker.get_model(m) for m in model]

    # error handling in case response is empty
    try:
        models = list(filter(lambda x: x['has_content'] is True, models))
        if verbose == 0:
            models = [(m['project_name']+".")*scoped_names+m['name'] for m in models]
    except:
        print("No results found.")
        return

    return models


# returns a list of explores in a given project and/or model
def get_explores(looker, project=None, model=None, scoped_names=0, verbose=0):
    explores = []
    if project is not None and model is None:
        # if project is specified, get all models in that project
        model_list = get_models(looker, project=project, verbose=1)
    elif project is None and model is None:
        # if no project or model are specified, get all models
        model_list = get_models(looker, verbose=1)
    else:
        # if project and model are specified or if project is not specified but model is.
        model_list = get_models(looker, model=model, verbose=1)

    # if verbose = 1, then return explore bodies otherwise return explore names which can be fully scoped with project name
    for mdl in model_list:
        if verbose == 1:
            explores.extend([looker.get_explore(model_name=mdl['name'], explore_name=explore['name']) for explore in mdl['explores']])
        else:
            explores.extend([(mdl['project_name']+'.'+mdl['name']+'.')*scoped_names+explore['name'] for explore in mdl['explores']])

    return explores


# returns a list of scoped fields of explores for a given model or explore
def get_explore_fields(looker, model=None, explore=None, scoped_names=0):
    fields = []
    explore_list = get_explores(looker, model=model, verbose=1)

    if explore is not None:
        # filter list based on explore names supplied
        explore_list = list(filter(lambda x: x['name'] == explore, explore_list))

    for explore in explore_list:
        fields.extend([(explore['model_name']+'.')*scoped_names+dimension['name'] for dimension in explore['fields']['dimensions']])
        fields.extend([(explore['model_name']+'.')*scoped_names+measure['name'] for measure in explore['fields']['measures']])
        fields.extend([(explore['model_name']+'.')*scoped_names+fltr['name'] for fltr in explore['fields']['filters']])

    return list(set(fields))


def get_views(looker, project=None, model=None, explore=None, scoped_names=0):
    fields = get_explore_fields(looker, model=None, explore=None, scoped_names=0)
    views = [field.split('.')[0] for field in fields]
    return list(set(views))


def get_projects(looker, project=None, verbose=0):
    if project is None:
        projects = looker.get_projects()
    else:
        projects = [looker.get_project(p) for p in project]

    if len(projects) == 0:
        print('No Projects Found.')
        return
    elif verbose == 0:
        projects = [p['id'] for p in projects]

    return projects


def get_project_files(looker, project=None):
    if project is None:
        projects = looker.get_projects()
        project_names = [project['id'] for project in projects]
    else:
        project_names = project

    project_data = []
    model_count = []
    view_count = []
    for project in project_names:
        project_files = looker.get_project_files(project)
        project_data.append({
                'project': project,
                'files': project_files
        })
        project_info = list(map(lambda x:
                                'model' if x['type'] == 'model' else
                                ('view' if x['type'] == 'view' else None),
                                project_files))
        model_count.append(project_info.count('model'))
        view_count.append(project_info.count('view'))

    return project_data, model_count, view_count


# builds a dictionary from a list of fields, in them form of
# {'view': 'view_name', 'fields': []}
def schema_builder(fields):
    schema = []
    distinct_fields = sorted(set(fields))

    view_field_pairs = [field.split('.') for field in distinct_fields]
    for key, group in groupby(view_field_pairs, lambda x: x[0]):
        schema.append({"view": key,
                       "fields": [i[1] for i in list(group)]
                       })

    return schema


# returns a representation of all models and the projects to which they belong
def schema_project_models(looker, project=None):
    schema = []
    for project in get_project_files(looker, project=None):
        models = []
        for file in project['files']:
            if file['type'] == 'model':
                models.append(file['title'])
            else:
                pass
        schema.append({
                        'project': project['project'],
                        'models': models
        })
    return schema


# def i__looker_query_body(model=None, timeframe):
# returns list of view scoped fields used within a given timeframe

def get_field_usage(looker, timeframe, model=None, project=None):
    if model is None:
        model = ','.join(get_models(looker))
    else:
        model = ','.join(model)
    body = {
            "model": "i__looker",
            "view": "history",
            "fields": ["query.model", "query.view", "query.formatted_fields",
                       "query.formatted_filters", "query.sorts",
                       "query.formatted_pivots", "history.query_run_count"],
            "filters": {"history.created_date": timeframe,
                        "query.model": model},
            "limit": "50000"
    }
    response = looker.run_inline_query("json", body)
    return {'response': response, 'model': model.split(',')}


def aggregate_usage(looker, timeframe, model, aggregation=None):
    field_usage = get_field_usage(looker, model, timeframe)
    response = field_usage['response']
    models = field_usage['model']
    formatted_fields = []
    for row in response:
        fields = []
        explore = row['query.view']
        model = row['query.model']
        run_count = row['history.query_run_count']
        fields.extend(parse(row['query.formatted_fields']))
        fields.extend(parse(row['query.formatted_filters']))
        fields.extend(parse(row['query.formatted_pivots']))
        fields.extend(parse(row['query.sorts']))
        formatted_fields.extend([model + '.' + explore + '.' + field + '.' +
                                str(run_count) for field in fields])
    aggregator_count = []
    aggregator = []

    if aggregation == 'field':
        for row in formatted_fields:
            field = '.'.join(row.split('.')[2:4])
            aggregator.append(field)
            count = int(row.split('.')[4])
            aggregator_count.append({
                'aggregator': field,
                'count': count
            })

        fields = [get_explore_fields(looker, model=[m]) for m in models]
        # flatten the list
        fields = [y for x in fields for y in x]
        [aggregator_count.append({'aggregator': field, 'count': 0}) for field in fields]

    if aggregation == 'view':
        for row in formatted_fields:
            view = row.split('.')[2]
            aggregator.append(view)
            count = int(row.split('.')[4])
            aggregator_count.append({
                'aggregator': view,
                'count': count
            })

        views = [get_views(looker, model=[model]) for model in models]
        # flatten the list
        views = [y for x in views for y in x]
        [aggregator_count.append({'aggregator': view, 'count': 0}) for view in views]

    if aggregation == 'explore':
        for row in formatted_fields:
            explore = row.split('.')[1]
            aggregator.append(explore)
            count = int(row.split('.')[4])
            aggregator_count.append({
                'aggregator': explore,
                'count': count
            })
        explores = [get_explores(looker, model=[model]) for model in models]
        # flatten the list
        explores = [y for x in explores for y in x]
        [aggregator_count.append({'aggregator': explore, 'count': 0}) for explore in explores]

    if aggregation == 'model':
        for row in formatted_fields:
            model = row.split('.')[0]
            aggregator.append(model)
            count = int(row.split('.')[4])
            aggregator_count.append({
                'aggregator': model,
                'count': count
            })
        models = get_models(looker, model=[model])
        models = [get_explores(looker, model=[model]) for model in models]
        # flatten the list
        models = [y for x in models for y in x]
        [aggregator_count.append({'aggregator': model, 'count': 0}) for model in models]

    c = Counter()

    for value in aggregator_count:
        c[value['aggregator']] += value['count']

    return dict(c)
    # return aggregator_count


# resturns a list of dictionaries in the format of
# {'model':'model_name', 'explores': ['explore_name1',...]}
def get_models_explores(looker, model):
    schema = []
    for model in get_models(looker, model):
        d = {'model': model['name'],
             'explores': [explore['name'] for explore in model['explores']]
             }
        schema.append(d)

    return(schema)


# returns a tree representation of a dictionary
def tree_maker(dict):
    tree_str = json.dumps(dict, indent=4)
    tree_str = tree_str.replace("\n    ", "\n")
    tree_str = tree_str.replace('"', "")
    tree_str = tree_str.replace(',', "")
    tree_str = tree_str.replace("{", "")
    tree_str = tree_str.replace("}", "")
    tree_str = tree_str.replace("    ", " | ")
    tree_str = tree_str.replace("  ", " ")
    tree_str = tree_str.replace("[", "")
    tree_str = tree_str.replace("]", "")

    return(tree_str)


# returns an instanstiated Looker object using the
# credentials supplied by the auth argument group
def authenticate(**kwargs):
    if kwargs['client_id'] and kwargs['client_secret']:
        # if client_id and client_secret are passed, then use them
        looker = LookerApi(host=kwargs['host'],
                           port=kwargs['port'],
                           token=kwargs['client_id'],
                           secret=kwargs['client_secret'])
    else:
        # otherwise, find credentials in config file
        try:
            f = open('config.yml')
            params = yaml.load(f)
            f.close()
        except:
            print('config.yml not found.')

        try:
            my_host = params['hosts'][kwargs['host']]['host']
            my_secret = params['hosts'][kwargs['host']]['secret']  # secret
            my_token = params['hosts'][kwargs['host']]['token']  # client_id
            looker = LookerApi(host=my_host,
                               port=kwargs['port'],
                               token=my_token,
                               secret=my_secret)
        except:
            print('%s host not found' % kwargs['host'])
            return

    return looker


if __name__ == "__main__":
    main()
