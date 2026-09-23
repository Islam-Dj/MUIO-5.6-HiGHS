"""Desktop server boundaries.

Changes are serialized per model within one server process: while a model is being
run or changed, other models can still be selected, read and edited.
"""
import threading
from flask import g, jsonify, request, session
from Classes.Base import Config
from Classes.Base.SafePaths import component, child

_case_locks = {}
_case_locks_guard = threading.Lock()
READ_POSTS = {'progress', 'getResultCSV', 'getDesc', 'getResultData', 'getParamFile',
              'readDataFile', 'validateInputs', 'viewData', 'viewTEData', 'getCases', 'getSession',
              'setSession', 'resultsExists'}
# Endpoints that create a new model: they do not depend on the selected model.
NEW_CASE_POSTS = {'uploadCase', 'uploadXls', 'importTemplate'}


def session_key(storage):
    """The key that signs the session.

    MUIO_SECRET_KEY is used when set. Otherwise a key is generated on first start and
    kept in the data folder, so the selected model survives a restart. The file is
    local to each installation and is never published.
    """
    import os
    import secrets
    from pathlib import Path
    configured = os.environ.get('MUIO_SECRET_KEY')
    if configured:
        return configured
    path = Path(storage) / '.session_key'
    try:
        stored = path.read_text(encoding='ascii').strip()
        if len(stored) >= 32:
            return stored
    except (OSError, UnicodeError):
        pass
    key = secrets.token_hex(32)
    try:
        path.write_text(key, encoding='ascii')
    except OSError:
        pass
    return key


def lock_for(case):
    """The lock that serializes changes to one model ('' for new models)."""
    with _case_locks_guard:
        return _case_locks.setdefault(case or '', threading.Lock())
PATH_FIELDS = {'casename', 'caserunname', 'oldcaserunname', 'modelname', 'case',
               'dataJson', 'file', 'template', 'osy-template', 'groupId', 'osy-casename'}


def install(app):
    @app.before_request
    def guard():
        endpoint = request.path.strip('/')
        payload = request.get_json(silent=True)
        if payload is not None and not isinstance(payload, dict):
            raise ValueError('The request must be a JSON object.')
        sources = [request.args, request.form, payload or {}]
        if isinstance((payload or {}).get('data'), dict):
            sources.append(payload['data'])
        for source in sources:
            for key in PATH_FIELDS:
                if key in source and source[key] is not None:
                    child(Config.DATA_STORAGE, component(source[key]))
        if session.get('osycase'):
            child(Config.DATA_STORAGE, session['osycase'])
        cases = (payload or {}).get('cases', [])
        if not isinstance(cases, list):
            raise ValueError('Cases must be a list of run names.')
        for name in cases:
            component(name)
        if 'resultsOnly' in (payload or {}) and not isinstance(payload['resultsOnly'], bool):
            raise ValueError('resultsOnly must be true or false.')
        selected = (payload or {}).get('casename') or session.get('osycase')
        if selected:
            for directory in ('res', 'view'):
                child(Config.DATA_STORAGE, selected, directory)
            run = (payload or {}).get('caserunname') or request.args.get('caserunname')
            if run:
                child(Config.DATA_STORAGE, selected, 'res', run)
        sync_routes = {'initSyncS3', 'uploadSync', 'deleteSync', 'updateSync',
                       'updateSyncParamFile', 'deleteResultsPreSync'}
        if endpoint in sync_routes and not Config.AWS_SYNC:
            return jsonify(status_code='error', message='Cloud synchronization is disabled.'), 404
        mutating = request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and endpoint not in READ_POSTS
        mutating = mutating or endpoint in ('initSyncS3', 'updateSyncParamFile', 'backupCase')
        if mutating:
            origin = request.headers.get('Origin')
            if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
                return jsonify(status_code='error', message='Cross-origin changes are not allowed.'), 403
            payload_ = payload or {}
            target = ('' if endpoint in NEW_CASE_POSTS else
                      payload_.get('casename') or payload_.get('modelname') or payload_.get('case')
                      or session.get('osycase') or '')
            lock = lock_for(target)
            if not lock.acquire(blocking=False):
                return jsonify(status_code='error', message='This model is being run or changed. '
                               'Please retry when it finishes.'), 409
            g.muio_write_lock = lock

    @app.teardown_request
    def release(_error):
        lock = getattr(g, 'muio_write_lock', None)
        if lock is not None:
            g.muio_write_lock = None
            lock.release()

    @app.errorhandler(ValueError)
    @app.errorhandler(KeyError)
    def invalid(error):
        return jsonify(status_code='error', message=str(error)), 400

    @app.errorhandler(FileNotFoundError)
    def missing(error):
        return jsonify(status_code='error', message=str(error)), 404
