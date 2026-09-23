import shutil
from flask import Blueprint, request, jsonify, send_file, after_this_request
from zipfile import ZipFile
from pathlib import Path
from werkzeug.utils import secure_filename
import os, time, json, glob

import tempfile
import uuid
import re
from zipfile import BadZipFile
from Classes.Base.CaseArchive import extract_case
from Classes.Base.SafePaths import child, component, within

from Classes.Case.HelpersClass import Helpers
from Classes.Base import Config
from Classes.Base.FileClass import File

upload_api = Blueprint('UploadRoute', __name__)

#File extension checking
def allowed_filename(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in Config.ALLOWED_EXTENSIONS

#File extension checking
def allowed_filename_xls(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in Config.ALLOWED_EXTENSIONS_XLS

def download_dir(prefix, local, bucket, client):
    """
    params:
    - prefix: pattern to match in s3
    - local: local path to folder in which to place files
    - bucket: s3 bucket with target contents
    - client: initialized s3 client object
    """
    keys = []
    dirs = []
    next_token = ''
    base_kwargs = {
        'Bucket':bucket,
        'Prefix':prefix,
    }
    while next_token is not None:
        kwargs = base_kwargs.copy()
        if next_token != '':
            kwargs.update({'ContinuationToken': next_token})
        results = client.list_objects_v2(**kwargs)
        contents = results.get('Contents')
        for i in contents:
            k = i.get('Key')
            if k[-1] != '/':
                keys.append(k)
            else:
                dirs.append(k)
        next_token = results.get('NextContinuationToken')
    for d in dirs:
        dest_pathname = os.path.join(local, d)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
    for k in keys:
        dest_pathname = os.path.join(local, k)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
        client.download_file(bucket, k, dest_pathname)

def upload_dir(s3, localDir, awsInitDir, bucketName, tag, prefix='\\'):
    """
    from current working directory, upload a 'localDir' with all its subcontents (files and subdirectories...)
    to a aws bucket
    Parameters
    ----------
    localDir :   localDirectory to be uploaded, with respect to current working directory
    awsInitDir : prefix 'directory' in aws
    bucketName : bucket in aws
    tag :        tag to select files, like *png
                 NOTE: if you use tag it must be given like --tag '*txt', in some quotation marks... for argparse
    prefix :     to remove initial '/' from file names

    Returns
    -------
    None
    """

    # mydirs daje listu svvih file i folder u localDir npr WebApp/DataStorage/Demo/genData.json
    mydirs = list(localDir.glob('**'))
    for mydir in mydirs:
        fileNames = glob.glob(os.path.join(mydir, tag))
        fileNames = [f for f in fileNames if not Path(f).is_dir()]
        #rows = len(fileNames)
        for i, FullfileName in enumerate(fileNames):
            #dobijemo ime file npr, genData.json
            fileName = str(FullfileName).replace(str(localDir), '')
            if fileName.startswith(prefix):  # only modify the text if it starts with the prefix
                fileName = fileName.replace(prefix, "", 1) # remove one instance of prefix
                fileName = fileName.replace('\\', '/')

            awsPath = str(awsInitDir) + '/' + str(fileName)
            # S3.resource.meta.client.upload_file(FullfileName, bucketName, awsPath)
            s3.resource.meta.client.upload_file(FullfileName, bucketName, awsPath)

def updateTimeslices(casename, storage=None):
    storage = storage or Config.DATA_STORAGE
    genDataPath = Path(storage, casename, 'genData.json')
    genData = File.readParamFile(genDataPath)
    ns = int(genData["osy-ns"])
    nd = int(genData["osy-dt"])
    genData["osy-se"] = []
    genData["osy-se"].append({"SeId": "SE_0", "Se": "1", "Desc": "Default season"})

    genData["osy-dt"] = []
    genData["osy-dt"].append({"DtId": "DT_0", "Dt": "1", "Desc": "Default day type"})

    genData["osy-dtb"] = []
    genData["osy-dtb"].append({"DtbId": "DTB_0", "Dtb": "1", "Desc": "Default dialy time bracket"})

    genData["osy-ts"] = []
    for season in range(ns):
        for day in range(nd):
            chunk = {}
            s = str(season + 1)
            d = str(day + 1)
            chunk['TsId'] = "S"+s+d
            chunk['Ts'] = "S"+s+d
            chunk["SE"] = "SE_0"
            chunk["DT"] = "DT_0"
            chunk["DTB"] = "DTB_0"
            chunk['Desc'] = "Default year split"
            genData["osy-ts"].append(chunk)
    File.writeFile( genData, genDataPath)
    #rename json files with timeslices
    RYTsPath = Path(storage, casename, 'RYTs.json')
    RYTsPath.write_text(RYTsPath.read_text().replace('YearSplit', 'TsId'))
    RYTTsPath = Path(storage, casename, 'RYTTs.json')
    RYTTsPath.write_text(RYTTsPath.read_text().replace('Timeslice', 'TsId'))
    RYCTsPath = Path(storage, casename, 'RYCTs.json')
    RYCTsPath.write_text(RYCTsPath.read_text().replace('Timeslice', 'TsId'))

def updateStorageSet(casename, storage=None):
    storage = storage or Config.DATA_STORAGE
    genDataPath = Path(storage, casename, 'genData.json')
    genData = File.readParamFile(genDataPath)

    genData["osy-stg"] = []

    File.writeFile( genData, genDataPath)

def updateGenData(casename, genData, storage=None):
    storage = storage or Config.DATA_STORAGE
    genDataPath = Path(storage, casename, 'genData.json')

    genData["osy-indicators"] = []

    File.writeFile( genData, genDataPath)

def updateViewDefintions(casename, genData, storage=None):
    storage = storage or Config.DATA_STORAGE

    viewDataPath = Path(storage,casename,'view','viewDefinitions.json')

    
    if not viewDataPath.exists():
        viewDefExisting = {"osy-views": {} }
        File.writeFile(viewDefExisting, viewDataPath)
    else:
        viewDefExisting = File.readParamFile(viewDataPath)


    # configPath = Path(storage, 'Variables.json')
    # vars = File.readParamFile(configPath)

    ##########
    customIndicators = genData['osy-indicators']
    techsMap = {tech['TechId']: tech['Tech'] for tech in genData["osy-tech"] }
    storagePath = Path(Config.DATA_STORAGE)
    VARIABLES = File.readParamFile(storagePath / 'Variables.json')
    INDICATORS = File.readParamFile(storagePath / 'Indicators.json')

    IND_GROUPED = Helpers.merge_all_indicators_grouped(INDICATORS, customIndicators, techsMap)

    vars = Helpers.merge_groups(VARIABLES, IND_GROUPED)

    ################


    viewDef = {}
    # for group, lists in vars.items():
    #     for list in lists:
    #         if list['id'] not in viewDefExisting["osy-views"]:
    #             viewDef[list['id']] = []
    #         else:
    #             viewDef[list['id']] = viewDefExisting["osy-views"][list['id']]



    for group, lists in vars.items():
        for list in lists:
            if list['id'] not in viewDefExisting["osy-views"]:      
                # Ako postoji indicator_type → izbriši ključ (ako je ranije kreiran)
                if "indicator_type" in list and list["indicator_type"]:
                    if list['id'] in viewDef:
                        del viewDef[list['id']]
                    else:
                        viewDef[list['id']] = []
                else:
                    viewDef[list['id']] = []
            else:
                if "indicator_type" in list and list["indicator_type"]:
                    viewDef[list['id']] = viewDefExisting["osy-views"][list['id']]
                else:           
                    viewDef[list['id']] = viewDefExisting["osy-views"][list['id']]


    viewData = {
        "osy-views": viewDef
    }
    File.writeFile( viewData, viewDataPath)

def updateTimeslices_OnlyTs(casename, storage=None):
    storage = storage or Config.DATA_STORAGE
    genDataPath = Path(storage, casename, 'genData.json')
    genData = File.readParamFile(genDataPath)
    ns = int(genData["osy-ns"])
    nd = int(genData["osy-dt"])
    genData["osy-ts"] = []
    for season in range(ns):
        for day in range(nd):
            chunk = {}
            s = str(season + 1)
            d = str(day + 1)
            chunk['TsId'] = "S"+s+d
            chunk['Ts'] = "S"+s+d
            chunk['Desc'] = "Default year split"
            genData["osy-ts"].append(chunk)
    File.writeFile( genData, genDataPath)
    #rename json files with timeslices
    RYTsPath = Path(storage, casename, 'RYTs.json')
    RYTsPath.write_text(RYTsPath.read_text().replace('YearSplit', 'TsId'))
    RYTTsPath = Path(storage, casename, 'RYTTs.json')
    RYTTsPath.write_text(RYTTsPath.read_text().replace('Timeslice', 'TsId'))
    RYCTsPath = Path(storage, casename, 'RYCTs.json')
    RYCTsPath.write_text(RYCTsPath.read_text().replace('Timeslice', 'TsId'))
def runtime_dir():
    path = Config.ROOT_DIR / '.runtime'
    path.mkdir(exist_ok=True)
    return path


@upload_api.route('/backupCase', methods=['GET'])
def backupCase():
    case = component(request.args.get('case'))
    case_path = child(Config.DATA_STORAGE, case)
    if not case_path.is_dir():
        raise FileNotFoundError('Case does not exist.')
    stream = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, dir=runtime_dir())
    with ZipFile(stream, 'w') as zipped:
        for path in case_path.rglob('*'):
            if path.is_file() and path.name != 'lp.lp':
                within(case_path, path.relative_to(case_path))
                if any(part.startswith('.') for part in path.relative_to(case_path).parts):
                    continue
                zipped.write(path, str(Path('WebAPP', 'DataStorage', case) / path.relative_to(case_path)))
    stream.seek(0)
    response = send_file(stream, download_name=case + '.zip', as_attachment=True)
    response.call_on_close(stream.close)
    return response


def handle_full_zip(file, filepath=None):
    # Migrate a private copy. Existing cases and application code are never extraction targets.
    with tempfile.TemporaryDirectory(prefix='import-', dir=runtime_dir()) as directory:
        staging = within(runtime_dir(), Path(directory).name)
        if filepath is None:
            if file is None or not allowed_filename(file.filename or ''):
                raise ValueError('Select a ZIP case archive.')
            filepath = staging / 'upload.zip'
            file.save(filepath)
        try:
            case, case_path = extract_case(filepath, staging / 'cases')
        except BadZipFile as error:
            raise ValueError('The uploaded file is not a valid ZIP archive.') from error
        destination = child(Config.DATA_STORAGE, case)
        if destination.exists():
            return jsonify(response=[{'status_code': 'warning', 'message': 'Case already exists: ' + case}]), 200
        gen = File.readFile(case_path / 'genData.json')
        version = gen.get('osy-version')
        if version not in ('1.0', '2.0', '3.0', '4.0', '4.5', '4.9', '5.0', '5.6'):
            raise ValueError('Unsupported case version: ' + str(version))
        gen['osy-casename'] = case
        if not isinstance(gen.get('osy-tech'), list):
            raise ValueError('Case technology definitions are missing or invalid.')
        gen.setdefault('osy-indicators', [])
        File.writeFile(gen, case_path / 'genData.json')
        storage = case_path.parent
        (case_path / 'view').mkdir(exist_ok=True)
        (case_path / 'res').mkdir(exist_ok=True)
        if not (case_path / 'view' / 'resData.json').exists():
            File.writeFile({'osy-cases': []}, case_path / 'view' / 'resData.json')
        if version in ('1.0', '2.0', '3.0', '4.0', '4.5', '4.9'):
            updateTimeslices(case, storage)
            updateStorageSet(case, storage)
        gen = File.readFile(case_path / 'genData.json')
        if version in ('1.0', '2.0', '3.0'):
            gen.setdefault('osy-techGroups', [])
            for technology in gen['osy-tech']:
                technology.setdefault('TG', [])
        gen.setdefault('osy-indicators', [])
        File.writeFile(gen, case_path / 'genData.json')
        updateViewDefintions(case, gen, storage)
        # Validate JSON before publication, including filenames stored in the run index.
        for path in case_path.rglob('*.json'):
            File.readFile(path)
        runs = File.readFile(case_path / 'view' / 'resData.json')
        for run in runs.get('osy-cases', []):
            component(run['Case'])
        os.rename(case_path, destination)
    return jsonify(response=[{'status_code': 'success', 'message': 'Case imported: ' + case, 'casename': case}]), 200


@upload_api.route('/uploadCase', methods=['POST'])
def uploadCase():
    file = request.files.get('file')
    identifier = request.form.get('dzuuid')
    if identifier is None:
        return handle_full_zip(file)
    if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', identifier):
        raise ValueError('Invalid upload identifier.')
    if file is None:
        raise ValueError('Missing upload chunk.')
    index = int(request.form.get('dzchunkindex', '-1'))
    count = int(request.form.get('dztotalchunkcount', '0'))
    if not 0 <= index < count <= 10000:
        raise ValueError('Invalid chunk index or count.')
    folder = child(runtime_dir(), 'chunks', identifier)
    folder.mkdir(parents=True, exist_ok=True)
    meta = folder / 'metadata.json'
    if meta.exists() and File.readFile(meta)['count'] != count:
        raise ValueError('Chunk count changed during upload.')
    File.writeFile({'count': count}, meta)
    temporary = folder / ('part-' + str(index))
    file.save(temporary)
    os.replace(temporary, folder / ('chunk-' + str(index)))
    received = sum((folder / ('chunk-' + str(i))).is_file() for i in range(count))
    if received < count:
        return jsonify(status='received {}/{}'.format(received, count)), 200
    final_zip = folder / 'upload.zip'
    with final_zip.open('wb') as output:
        total = 0
        for i in range(count):
            chunk = folder / ('chunk-' + str(i))
            total += chunk.stat().st_size
            if total > 8 * 1024 ** 3:
                raise ValueError('Upload exceeds 8 GiB.')
            with chunk.open('rb') as source:
                shutil.copyfileobj(source, output, 1024 * 1024)
    try:
        return handle_full_zip(None, final_zip)
    finally:
        within(runtime_dir(), folder.relative_to(runtime_dir()))
        shutil.rmtree(folder)


@upload_api.route('/uploadXls', methods=['POST'])
def uploadXls():
    try: 
        msg = []
        submitted_storage =  request.files.to_dict()
        for files in submitted_storage.items():
            file = files[1]
            submitted_file = file.filename
            
            case = os.path.splitext(submitted_file)[0]
            filename = secure_filename(submitted_file)

            if submitted_file and allowed_filename_xls(submitted_file):
                filename = secure_filename(submitted_file)
                #spasiti zip u data storage
                file.save(os.path.join(Config.DATA_STORAGE, filename))

                #ako ima space u umenu rename file
                # filename_nosapces = filename[:]
                # filename_nosapces.replace(" ","")
                # if( filename_nosapces != filename):
                #     os.rename(os.path.join(Config.DATA_STORAGE, filename), os.path.join(Config.DATA_STORAGE, filename_nosapces))
                #     filename = filename_nosapces
        
                msg.append({
                    "message": "Template " + submitted_file +" have been uploaded!",
                    "status_code": "success",
                    "casename": case,
                    "template": filename
                })
            else:
                msg.append({
                    "message": "Template " + submitted_file +" is not valid .xlsx file!",
                    "status_code": "warning",
                    "casename": case,
                    "template": filename
                })

        response = {
            "response" :msg
        }

        return jsonify(response), 200
    except(IOError):
        raise IOError
    except OSError:
        raise OSError