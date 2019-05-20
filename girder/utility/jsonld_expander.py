from copy import deepcopy
from girder.models.activity import Activity as ActivityModel
from girder.models.screen import Screen as ScreenModel
from pyld import jsonld
import json


def check_for_unexpanded_value_constraints(item_exp):
    vc = item_exp[0]
    if 'https://schema.repronim.org/valueconstraints' in vc.keys():
        vc = vc['https://schema.repronim.org/valueconstraints'][0]
        if isinstance(vc, dict):
            if "@id" in vc.keys():
                return(True)

    return(False)


def expand(obj, keepUndefined=False):
    newObj = jsonld.expand(obj)
    newObj = newObj[0] if (
        isinstance(newObj, list) and len(newObj)==1
    ) else newObj
    if isinstance(
        newObj,
        dict
    ):
        newObj.update({
            k: obj[k] for k in obj.keys() if k not in keyExpansion(
                list(newObj.keys())
            )
        })
        return(newObj)
    else:
        return([expand(n, keepUndefined) for n in newObj])


def expand_value_constraints(original_items_expanded):
    items_expanded = deepcopy(original_items_expanded)
    for item, item_exp in original_items_expanded.items():
        # check if we need to expand valueConstraints
        vc = item_exp[0]
        if 'https://schema.repronim.org/valueconstraints' in vc.keys():
            if check_for_unexpanded_value_constraints(item_exp):
                vc = expand(
                    item_exp[0][
                        'https://schema.repronim.org/valueconstraints'
                    ][0]['@id']
                )
                items_expanded[item][0][
                    'https://schema.repronim.org/valueconstraints'
                ][0] = vc
        else:
            multipart_activities = get_activities(item_exp)
            items_expanded.update(multipart_activities)
    return(items_expanded)


def formatLdObject(obj, mesoPrefix='folder', user=None, keepUndefined=False):
    """
    Function to take a compacted JSON-LD Object within a Girder for Mindlogger
    database and return an exapanded JSON-LD Object including an _id.

    :param obj: Compacted JSON-LD Object
    :type obj: dict or list
    :param mesoPrefix: Girder for Mindlogger entity type, defaults to 'folder'
                       if not provided
    :type mesoPrefix: str
    :param user: User making the call
    :type user: User
    :returns: Expanded JSON-LD Object (dict or list)
    """
    if obj is None:
        return(None)
    if type(obj)==list:
        return([formatLdObject(obj, mesoPrefix) for o in obj])
    if not type(obj)==dict:
        raise TypeError("JSON-LD must be an Object or Array.")
    newObj = obj.get('meta', obj)
    newObj = newObj.get(mesoPrefix, newObj)
    newObj = expand(newObj, keepUndefined=keepUndefined)
    if type(newObj)==list and len(newObj)==1:
        newObj = newObj[0]
    if type(newObj)==dict:
        newObj['_id'] = "/".join([mesoPrefix, str(obj.get('_id', 'undefined'))])
    if mesoPrefix=='applet':
        applet = {'applet': newObj}
        applet['activities'] = {
            activity.get(
                'url',
                activity.get('@id')
            ): formatLdObject(
                ActivityModel().load(
                    activity.get('_id')
                ) if '_id' in activity else ActivityModel().importActivity(
                        url=activity.get(
                            'url',
                            activity.get('@id')
                        ),
                        applet=newObj.get(
                            '_id'
                        ).split('/')[1] if newObj.get(
                            '_id',
                            ''
                        ).startswith('applet') else None,
                        user=user
                ),
                'activity',
                user
            ) for order in newObj[
                "https://schema.repronim.org/order"
            ] for activity in order.get("@list", [])
        }
        applet['items'] = {
            screen.get(
                'url',
                screen.get('@id')
            ): formatLdObject(
                ScreenModel().load(
                    screen.get('_id'),
                    level=AccessType.READ,
                    user=user,
                    force=True
                ) if '_id' in screen else ScreenModel().importScreen(
                    url=screen.get(
                        'url',
                        screen.get('@id')
                    ),
                    activity=activity.get('_id').split(
                        '/'
                    )[1] if activity.get('_id').startswith(
                        'activity'
                    ) else ActivityModel().importActivity(
                        activity.get(
                            'url',
                            activity.get('@id')
                        ),
                        applet=applet.get('_id'),
                        user=user
                    ),
                    user=user
                ),
                'screen',
                user
            ) for activityURL, activity in applet.get(
                'activities',
                {}
            ).items() for order in activity.get(
                "https://schema.repronim.org/order",
                []
            ) for screen in order.get("@list", order.get("@set", []))
        }
        print(applet['items'])
        return(applet)
    if mesoPrefix=='activity':
        activity = newObj
    return(newObj)


def keyExpansion(keys):
    return(list(set([
        k.split(delimiter)[-1] for k in keys for delimiter in [
            ':',
            '/'
        ] if delimiter in k
    ] + [
        k for k in keys if (':' not in k and '/' not in k)
    ])))