import json as sj
import argparse
import logging
from glob import glob
import os
from fnmatch import fnmatch
import configparser
from tqdm import tqdm
#import imp
import importlib
import pprint
# from distutils.version import LooseVersion
script_dir = os.path.dirname(os.path.realpath(__file__))
try:
    spec = importlib.util.spec_from_file_location("veris_logger", script_dir + "/veris_logger.py")
    veris_logger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(veris_logger)
    # veris_logger = imp.load_source("veris_logger", script_dir + "/veris_logger.py")
except:
    print("Script dir: {0}.".format(script_dir))
    raise

cfg = {
    'log_level': 'warning',
    'log_file': None,
    'countryfile':'./all.json'
}

def getCountryCode(countryfile):
    country_codes = sj.loads(open(countryfile).read())
    country_code_remap = {'Unknown': '000000'}
    for eachCountry in country_codes:
        try:
            country_code_remap[eachCountry['alpha-2']] = \
                eachCountry['region-code']
        except:
            country_code_remap[eachCountry['alpha-2']] = "000"
        try:
            country_code_remap[eachCountry['alpha-2']] += \
                eachCountry['sub-region-code']
        except:
            country_code_remap[eachCountry['alpha-2']] += "000"
    return country_code_remap


def getField(current, txt):
    tsplit = txt.split('.', 1)
    if tsplit[0] in current:
        result = current[tsplit[0]]
        if len(tsplit) > 1:
            result = getField(result, tsplit[1])
    else:
        result = None
    return result


def grepText(incident, searchFor):
    txtFields = ['summary', "notes", "victim.notes", "actor.external.notes",
                 "actor.internal.notes", "actor.partner.notes",
                 "actor.unknown.notes", "action.malware.notes",
                 "action.hacking.notes", "action.social.notes",
                 "action.misuse.notes", "action.physical.notes",
                 "action.error.notes", "action.environmental.notes",
                 "asset.notes", "attribute.confidentiality.notes",
                 "attribute.integrity.notes", "attribute.availability.notes",
                 "impact.notes", "plus.analyst_notes", "plus.pci.notes"]
    foundAny = False
    for txtField in txtFields:
        curText = getField(incident, txtField)
        if isinstance(curText, str): # replaced basestr with str per 2to3. - GDB 181109
          if searchFor.lower() in curText:
              foundAny = True
              break
        # could be extended to look for fields in lists
    return foundAny


def main(cfg):
    veris_logger.updateLogger(cfg)

    last_version = "1.3.3"
    version = "1.3.4"
 
    if cfg.get('log_level', '').lower() == "debug":
        pprint.pprint(cfg) # DEBUG

    logging.info("Converting files from {0} to {1}.".format(cfg["input"], cfg["output"]))
    for root, dirnames, filenames in tqdm(os.walk(cfg['input'])):
      logging.info("starting parsing of directory {0}.".format(root))
      # filenames = filter(lambda fname: fnmatch(fname, "*.json"), filenames)
      filenames = [fname for fname in filenames if fnmatch(fname, "*.json")] # per 2to3. - GDB 181109
      if filenames:
        dir_ = os.path.join(cfg['output'], root[len(cfg['input']):]) # if we don't strip the input, we get duplicate directories 
        logging.info("Output directory is {0}.".format(dir_))
        if not os.path.isdir(dir_):
            os.makedirs(dir_)
        for fname in filenames:
            in_fname = os.path.join(root,fname)
            out_fname = os.path.join(dir_, fname)

            logging.info("Now processing %s" % in_fname)
            try:
                incident = sj.loads(open(in_fname).read())
            except sj.JSONDecodeError:
                logging.warning(
                    "ERROR: %s did not parse properly. Skipping" % in_fname)
                continue

            if 'assets' not in incident.get('asset', {}):
                raise KeyError("Asset missing from assets in incident {0}.".format(fname))


            # if the record is already version 1.3.3, skip it. This can happen if there are mixed records
            if incident.get('schema_version', last_version) != last_version:
                if incident.get('schema_version', '') != version:
                    logging.warning("Incident {0} is version {1} instead of {2} and can therefore not be updated.".format(fname, incident.get('schema_version', 'NONE'), last_version))
                continue

            # Update the schema version
            incident['schema_version'] = version

            # EXAMPLE UPDATE
#             # Replace asset S - SCADA with S - ICS
#             # Issue 104, Commit f8b7387
#             # if "S - SCADA" in incident.get("asset", {}).get("assets", []):
#                 # incident["asset"]["assets"] = [e.replace("S - SCADA", "S - ICS") for e in incident["asset"]["assets"]]  
#             incident["asset"]["assets"] = [dict(e, **{u"variety": u"S - ICS"}) if e.get(u"variety", "") ==  u"S - SCADA" else e for e in incident["asset"]["assets"]] 


            ### Hierarchical Field
            # `asset.assets.variety.U - Desktop or laptop` is a parent of `asset.assets.variety.U - Desktop` and `asset.assets.variety.U - Laptop`
            # per vz-risk/VERIS issue #263
            if 'assets' in incident.get('asset', {}):
                if ('U - Desktop' in [item.get("variety", "") for item in incident['asset']['assets']] or \
                'U - Laptop' in [item.get("variety", "") for item in incident['asset']['assets']]):
                    incident['asset']['assets'].append({'variety': 'U - Desktop or laptop'})


            ### Hierarchical Field
            # `action.malware.variety.Email` is a parent of `action.malware.variety.Email attachment`, `action.malware.variety.Email autoexecute`, `action.malware.variety.Email link`, `action.malware.variety.Email other`, and `action.malware.variety.Email unknown`
            # per vz-risk/VERIS issue #232
            if 'variety' in incident.get('action', {}).get('malware', {}):
                if ('Email attachment' in incident['action']['malware'].get('variety', []) or \
                'Email autoexecute' in incident['action']['malware'].get('variety', []) or \
                'Email link' in incident['action']['malware'].get('variety', []) or \
                'Email other' in incident['action']['malware'].get('variety', []) or \
                'Email unknown' in incident['action']['malware'].get('variety', [])):
                    incident['action']['malware']['variety'].append('Email')


            ### Convert plus.attribute.confidentiality.credit_monitoring to a categorical field
            # per vz-risk/VERIS issue #260 
            if 'credit_monitoring' in incident.get('plus', {}).get('attribute', {}).get('confidentiality'):
                if incident['plus']['attribute']['confidentiality']['credit_monitoring'].upper() == 'N':
                    incident['plus']['attribute']['confidentiality']['credit_monitoring'] = 'No'
                elif incident['plus']['attribute']['confidentiality']['credit_monitoring'].upper() == 'U':
                    incident['plus']['attribute']['confidentiality']['credit_monitoring'] = 'Unknown'
                elif incident['plus']['attribute']['confidentiality']['credit_monitoring'].upper() == 'UNKNOWN':
                    incident['plus']['attribute']['confidentiality']['credit_monitoring'] = 'Unknown'
                elif incident['plus']['attribute']['confidentiality']['credit_monitoring'].upper() != '':
                    incident['plus']['attribute']['confidentiality']['credit_monitoring'] = 'Yes'
                else:
                    _ = incident['plus']['attribute']['confidentiality'].pop('credit_monitoring')
            # Ensure plus.attribute.confidentiality.credit_monitoring > 0 per new validation
            if 'credit_monitoring_years' in incident.get('plus', {}).get('attribute', {}).get('confidentiality'):
                if incident['plus']['attribute']['confidentiality']['credit_monitoring_years'] <= 0:
                    _ = incident['plus']['attribute']['confidentiality'].pop('credit_monitoring_years')


            ### Convert plus.attribute.confidentiality.partner_data to a categorical field
            # per vz-risk/VERIS issue #259
            if 'partner_data' in incident.get('plus', {}).get('attribute', {}).get('confidentiality'):
                if incident['plus']['attribute']['confidentiality']['partner_data'][0].upper() == 'N':
                    incident['plus']['attribute']['confidentiality']['partner_data'] = 'No'
                elif incident['plus']['attribute']['confidentiality']['partner_data'][0].upper() == 'U':
                    incident['plus']['attribute']['confidentiality']['partner_data'] = 'Unknown'
                elif incident['plus']['attribute']['confidentiality']['partner_data'][0].upper() == 'Y':
                    incident['plus']['attribute']['confidentiality']['partner_data'] = 'Y'
                elif incident['plus']['attribute']['confidentiality']['partner_data'][0].upper() == 'O':
                    incident['plus']['attribute']['confidentiality']['partner_data'] = 'Other'
                else:
                    _ = incident['plus']['attribute']['confidentiality'].pop('partner_data')
            # Ensure plus.attribute.confidentiality.partner_number > 0 per new validation
            if 'partner_number' in incident.get('plus', {}).get('attribute', {}).get('confidentiality'):
                if incident['plus']['attribute']['confidentiality']['partner_number'] <= 0:
                    _ = incident['plus']['attribute']['confidentiality'].pop('partner_number')


            ### Convert most cloud enumerations into hacking action varieties
            # per vz-risk/VERIS issue #225 and #236
            if 'cloud' in incident.get('asset', {}):
                cloud = incident['asset'].pop('cloud')
                if cloud == 'Customer attack':
                    if 'hacking' not in incident['action']:
                        incident['action']['hacking'] = {'variety':['Unknown'], 'vector':['Inter-tenant']}
                    else:
                        incident['action']['hacking']['vector'].append("Inter-tenant")
                elif cloud == 'Hosting error':
                    if 'error' not in incident['action']:
                        incident['action']['error'] = {'variety':['Misconfiguration'], 'vector':['Unknown']}
                    elif 'Misconfiguration' not in incident['action']['error']['variety']:
                        incident['action']['error']['variety'].append("Misconfiguration")
                    else:
                        pass # Misconfiguration is already in action.error.variety
                    incident['asset']['cloud'] = ['External Cloud Asset(s)']
                elif cloud == 'Hosting governance':
                    if 'error' not in incident['action']:
                        incident['action']['error'] = {'variety':['Process'], 'vector':['Unknown']}
                    elif 'Process' not in incident['action']['error']['variety']:
                        incident['action']['error']['variety'].append("Process")
                    else:
                        pass # Process is already in action.error.variety
                    incident['asset']['cloud'] = ['External Cloud Asset(s)']
                    for actor in incident['actor']:
                        if 'Secondary' not in incident['actor'][actor]['motive']:
                            incident['actor'][actor]['motive'].append('Secondary')
                elif cloud == "Hypervisor": 
                    if 'hacking' not in incident['action']:
                        incident['action']['hacking'] = {'variety':['Unknown'], 'vector':['Hypervisor']}
                    else:
                        incident['action']['hacking']['vector'].append("Hypervisor")
                elif cloud == "Parnter application":
                    if 'hacking' not in incident['action']:
                        incident['action']['hacking'] = {'variety':['Exploit vuln'], 'vector':['Unknown']}
                    elif 'Process' not in incident['action']['error']['variety']:
                        incident['action']['hacking']['variety'].append("Exploit vuln")
                    else:
                        pass # Exploit vuln is already in action.hacking.variety
                    for actor in incident['actor']:
                        if 'Secondary' not in incident['actor'][actor]['motive']:
                            incident['actor'][actor]['motive'].append('Secondary')
                elif cloud == "User breakout":
                    if 'hacking' not in incident['action']:
                        incident['action']['hacking'] = {'variety':['User breakout'], 'vector':['Unknown']}
                    else:
                        incident['action']['hacking']['variety'].append("User breakout")
                elif cloud == 'NA':
                    incident['asset']['cloud'] = ['Unknown']
                elif cloud == 'No':
                    incident['asset']['cloud'] = ['NA']
                elif cloud == 'Other':
                    incident['asset']['cloud'] = ['Other']
                elif cloud == 'Unknown':
                    incident['asset']['cloud'] = ['Unknown']


            ### action.social.target.End-user defined as 'End-user or regular employee' is being split into action.social.target.End-user and action.social.target.Other employee
            # per vz-risk/VERIS issue #150
            if 'End-user' in incident.get('action', {}).get('social', {}).get('target', []):
                incident['action']['social']['target'] = [enum if enum != "End-user" else "End-user or employee" for enum in incident['action']['social']['target']]


            # Now to save the incident
            logging.info("Writing new file to %s" % out_fname)
            with open(out_fname, 'w') as outfile:
                sj.dump(incident, outfile, indent=2, sort_keys=True, separators=(',', ': '))


if __name__ == '__main__':
    descriptionText = "Converts VERIS 1.3.3 incidents to v1.3.4"
    helpText = "output directory to write new files. Default is to overwrite."
    parser = argparse.ArgumentParser(description=descriptionText)
    parser.add_argument("-l","--log_level",choices=["critical","warning","info","debug"], help="Minimum logging level to display")
    parser.add_argument('--log_file', help='Location of log file')
    parser.add_argument("-i", "--input", required=True,
                        help="top level folder to search for incidents")
    parser.add_argument("-o", "--output",
                        help=helpText)
    # parser.add_argument('--countryfile', help='The json file holdering the country mapping.')
    parser.add_argument('--conf', help='The location of the config file', default="../user/data_flow.cfg")
    args = parser.parse_args()
    args = {k:v for k,v in vars(args).items() if v is not None}

    # logging_remap = {'warning':logging.WARNING, 'critical':logging.CRITICAL, 'info':logging.INFO, 'debug':logging.DEBUG} # defined above. - gdb 080716

    # Parse the config file
    try:
        config = configparser.ConfigParser()
        config.readfp(open(args["conf"]))
        cfg_key = {
            'GENERAL': ['report', 'input', 'output', 'analysis', 'year', 'force_analyst', 'version', 'database', 'check'],
            'LOGGING': ['log_level', 'log_file'],
            'REPO': ['veris', 'dbir_private'],
            'VERIS': ['mergedfile', 'enumfile', 'schemafile', 'labelsfile', 'countryfile']
        }
        for section in cfg_key.keys():
            if config.has_section(section):
                for value in cfg_key[section]:
                    if value.lower() in config.options(section):
                        cfg[value] = config.get(section, value)
        veris_logger.updateLogger(cfg)
        logging.debug("config import succeeded.")
    except Exception as e:
        logging.warning("config import failed with error {0}.".format(e))
        #raise e
        pass
    # place any unique config file parsing here
    if "input" in cfg:
        cfg["input"] = [l.strip() for l in cfg["input"].split(" ,")]  # spit to list

    cfg.update(args)

    if "output" not in cfg:
        cfg["output"] = cfg["input"]

    veris_logger.updateLogger(cfg)

    # country_region = getCountryCode(cfg['countryfile'])

    # assert args.path != args.output, "Source and destination must differ"

    main(cfg)

