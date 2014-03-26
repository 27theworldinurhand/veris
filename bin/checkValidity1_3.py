#TODO Need to make this parse an argument for the file path that is going to be examined
#TODO Make it so you can specify these things in a config file rather than command line. Command line
# should override config file. Both should override built-in defaults
#TODO should specify a default config file.
#TODO should check if the config file exists before trying to use it.

import simplejson
import nose
import os
from jsonschema import validate, ValidationError
import argparse
import ConfigParser
import logging

def buildSchema(schema,enum):
# All of the action enumerations
    for each in ['hacking','malware','social','error','misuse','physical']:
        schema['properties']['action']['properties'][each]['properties']['variety']['items']['enum'] = enum['action'][each]['variety']
        schema['properties']['action']['properties'][each]['properties']['vector']['items']['enum'] = enum['action'][each]['vector']
    schema['properties']['action']['properties']['environmental']['properties']['variety']['items']['enum'] = enum['action']['environmental']['variety']
    schema['properties']['action']['properties']['physical']['properties']['location']['items']['enum'] = enum['action']['physical']['location']
    schema['properties']['action']['properties']['social']['properties']['target']['items']['enum'] = enum['action']['social']['target']

# actor enumerations
    for each in ['external','internal','partner']:
        schema['properties']['actor']['properties'][each]['properties']['motive']['items']['enum'] = enum['actor']['motive']
    schema['properties']['actor']['properties']['external']['properties']['variety']['items']['enum'] = enum['actor']['external']['variety']
    schema['properties']['actor']['properties']['internal']['properties']['variety']['items']['enum'] = enum['actor']['internal']['variety']
    schema['properties']['actor']['properties']['external']['properties']['country']['items']['enum'] = enum['country']
    schema['properties']['actor']['properties']['partner']['properties']['country']['items']['enum'] = enum['country']

# asset properties
    schema['properties']['asset']['properties']['assets']['items']['properties']['variety']['pattern'] = '|'.join(enum['asset']['variety'])
    for each in ['accessibility','cloud','hosting','management','ownership']:
        schema['properties']['asset']['properties'][each]['pattern'] = '|'.join(enum['asset'][each])

# attribute properties
    schema['properties']['attribute']['properties']['availability']['properties']['variety']['items']['enum'] = enum['attribute']['availability']['variety']
    schema['properties']['attribute']['properties']['availability']['properties']['duration']['properties']['unit']['pattern'] = '|'.join(enum['timeline']['unit'])
    schema['properties']['attribute']['properties']['confidentiality']['properties']['data']['items']['properties']['variety']['pattern'] = '|'.join(enum['attribute']['confidentiality']['data']['variety'])
    schema['properties']['attribute']['properties']['confidentiality']['properties']['data_disclosure']['pattern'] = '|'.join(enum['attribute']['confidentiality']['data_disclosure'])
    schema['properties']['attribute']['properties']['confidentiality']['properties']['state']['items']['enum'] = enum['attribute']['confidentiality']['state']
    schema['properties']['attribute']['properties']['integrity']['properties']['variety']['items']['enum'] = enum['attribute']['integrity']['variety']

# impact
    schema['properties']['impact']['properties']['iso_currency_code']['patter'] = '|'.join(enum['iso_currency_code'])
    schema['properties']['impact']['properties']['loss']['items']['properties']['variety']['pattern'] = '|'.join(enum['impact']['loss']['variety'])
    schema['properties']['impact']['properties']['loss']['items']['properties']['rating']['pattern'] = '|'.join(enum['impact']['loss']['rating'])
    schema['properties']['impact']['properties']['overall_rating']['patter'] = '|'.join(enum['impact']['overall_rating'])

# timeline
    for each in ['compromise','containment','discovery','exfiltration']:
        schema['properties']['timeline']['properties'][each]['properties']['unit']['pattern'] = '|'.join(enum['timeline']['unit'])

# victim
    schema['properties']['victim']['properties']['country']['pattern'] = '|'.join(enum['country'])
    schema['properties']['victim']['properties']['employee_count']['pattern'] = '|'.join(enum['victim']['employee_count'])
    schema['properties']['victim']['properties']['revenue']['properties']['iso_currency_code']['pattern'] = '|'.join(enum['iso_currency_code'])

# Randoms
    for each in ['confidence','cost_corrective_action','discovery_method','security_incident','targeted']:
        schema['properties'][each]['pattern'] = '|'.join(enum[each])

    return schema
# end of buildSchema()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Checks a set of json files to see if they are valid VERIS incidents")
    parser.add_argument("-s","--schema", help="schema file to validate with", default="../verisc.json")
    parser.add_argument("-e","--enum", help="enumeration file to validate with",default="../verisc-enum.json")
    parser.add_argument("-l","--logging",choices=["critical","warning","info"], help="Minimum logging level to display", default="warning")
    parser.add_argument("-p","--path", help="comma-separated list of paths to search for incidents", default="../data")
    args = parser.parse_args()
    logging_remap = {'warning':logging.WARNING, 'critical':logging.CRITICAL, 'info':logging.INFO}
    logging.basicConfig(level=logging_remap[args.logging])
    logging.info("Now starting checkValidity.")

    config = ConfigParser.ConfigParser()
    path_to_parse = config.get('VERIS', 'datapath')
    data_path = path_to_parse.split(',')
    if args.path:
        data_path.append(args.path)

    try:
        sk = simplejson.loads(open(args.schema).read())
    except IOError:
        logging.critical("ERROR: schema file not found. Cannot continue.")
        exit(1)
    except simplejson.scanner.JSONDecodeError:
        logging.critical("ERROR: schema file is not parsing properly. Cannot continue.")
        exit(1)

    try:
        en = simplejson.loads(open(args.enum).read())
    except IOError:
        logging.critical("ERROR: enumeration file is not found. Cannot continue.")
        exit(1)
    except simplejson.scanner.JSONDecodeError:
        logging.critical("ERROR: enumeration file is not parsing properly. Cannot continue.")
        exit(1)

# Now we can build the schema which will be used to validate our incidents
    schema = buildSchema(sk,en)
    logging.info("schema assembled successfully.")
    # Now we will loop through all the files in the destination path(s) and use validate on them
    for eachPath in data_path:
      print(eachPath)

    logging.info("checkValidity complete")
