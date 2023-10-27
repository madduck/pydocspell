import requests
from requests_toolbelt.multipart import encoder
import logging
import re
import enum

from .metadata import UploadMetadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class APIWrapper:
    DEFAULT_VERSION = 1
    DEFAULT_API_PATH = "/api/v{version}"

    class State(enum.Enum):
        INIT = object()
        LOGGEDIN = object()
        LOGGEDOUT = object()
        SHUTDOWN = object()

        def set_info(self, info):
            self._info = info

        def __str__(self):
            ret = f"{self.name.lower()}"
            if self._info:
                return f"{ret}({self._info})"
            return ret

    class NotAuthenticated(Exception):
        pass

    class NotAuthorized(Exception):
        pass

    def __init__(
        self, baseurl, *, session=None, version=DEFAULT_VERSION, debug=True
    ):
        self._session = session or requests.Session()
        self._baseurl = baseurl.strip("/")
        self._state = APIWrapper.State.INIT
        self._debug = debug
        if "/api/" in baseurl:
            logger.warning(
                f"/api/ in base URL, ignoring {version=}: {baseurl=}"
            )
            self._version = int(re.search(r"/v(\d)", baseurl).group(1))
            parts = baseurl.split("/api")
            self._baseurl = parts[0]
            self._apiurl = baseurl
        else:
            self._version = version
            self._apiurl = APIWrapper.make_api_url(baseurl)

            f"{baseurl}{APIWrapper.DEFAULT_API_PATH}".format(version=version)

    version = property(lambda s: s._version)
    baseurl = property(lambda s: s._baseurl)
    apiurl = property(lambda s: s._apiurl)
    state = property(lambda s: s._state)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        import bdb

        if self._debug and exc_type not in (
            None,
            KeyboardInterrupt,
            bdb.BdbQuit,
        ):
            try:
                import ipdb

                ipdb.set_trace()
            except ImportError:
                pass

        self.logout()
        self._session.close()
        self._session = None
        self._state = APIWrapper.State.SHUTDOWN

    def __str__(self):
        return f"<APIWrapper url={self.apiurl} {self.state}>"

    def __repr__(self):
        return str(self)

    @classmethod
    def make_api_url(cls, baseurl, *, version=None):
        version = version or cls.DEFAULT_VERSION
        ret = f"{baseurl}{APIWrapper.DEFAULT_API_PATH}".format(version=version)
        logger.debug(f"make_api_url({baseurl}, version={version}) → {ret}")
        return ret

    @classmethod
    def make_endpoint_url(
        cls, baseurl, endpoint, *, apiurl=None, version=None
    ):
        apiurl = apiurl or cls.make_api_url(baseurl, version=version)
        ret = "/".join((apiurl, endpoint))
        logger.debug(
            f"make_endpoint_url({baseurl}, {endpoint}, "
            f"apiurl={apiurl}, version={version}) → {ret}"
        )
        return ret

    def _request(
        self,
        method,
        endpoint,
        *,
        apiurl=None,
        json=None,
        data=None,
        files=None,
        **kwargs,
    ):
        url = APIWrapper.make_endpoint_url(
            self._baseurl, endpoint, apiurl=apiurl
        )
        logger.debug(f"> {method} {url}")
        if files:
            logger.debug(f"> {files=}")
        if data:
            logger.debug(f"> {data=}")
        if json:
            logger.debug(f"> {json=}")
        resp = self._session.request(
            method,
            url,
            json=json,
            files=files,
            data=data,
            **kwargs,
        )
        try:
            json = resp.json()
            if "token" in json:
                json["token"] = "XXX"
        except requests.exceptions.JSONDecodeError:
            json = {}
        logger.debug(f"< {resp.status_code} {json=}")
        return resp

    def get_docspell_version(self):
        resp = self._request("GET", "api/info/version", apiurl=self.baseurl)
        return resp.json()

    def login(self, collective, username, password, rememberme=True):
        data = {
            "account": "/".join((collective, username)),
            "password": password,
            "rememberMe": rememberme,
        }
        resp = self._request("POST", "open/auth/login", json=data)
        if resp.status_code == requests.codes.ok:
            self._state = APIWrapper.State.LOGGEDIN
            self._state.set_info(f"user={collective}/{username}")
            logger.info(f"Logged in as {collective}/{username}")
        return resp.json()

    def logout(self):
        if self.state == APIWrapper.State.LOGGEDIN:
            self._request("POST", "sec/auth/logout")
            self._state = APIWrapper.State.LOGGEDOUT
            logger.info("Logged out")
        return {}

    def _upload_multiple(
        self,
        endpoint,
        file_and_name_tuples,
        *,
        transfer_cb=None,
        metadata=None,
    ):
        formdata = []
        if metadata:
            formdata.append(("meta", metadata.to_json()))

        for fileobj, name in file_and_name_tuples:
            formdata.append(("file", (name, fileobj)))

        enc = encoder.MultipartEncoder(formdata)
        if callable(transfer_cb):
            enc = encoder.MultipartEncoderMonitor(enc, transfer_cb)

        resp = self._request(
            "POST",
            endpoint,
            data=enc,
            headers={"Content-Type": enc.content_type},
        )
        return resp.json()

    def _upload_single(
        self, endpoint, fileobj, name=None, *, transfer_cb=None, metadata=None
    ):
        if not callable(getattr(fileobj, "read", None)):
            raise ValueError(f"{fileobj=} is not an open file/stream")

        name = name or fileobj.name
        if metadata and metadata.multiple:
            logger.warning(f"meta[multiple] but single file {name}")
        return self._upload_multiple(
            endpoint,
            ((fileobj, name),),
            transfer_cb=transfer_cb,
            metadata=metadata,
        )

    def upload_multiple(
        self, file_and_name_tuples, *, transfer_cb=None, metadata=None
    ):
        return self._upload_multiple(
            "sec/upload/item",
            file_and_name_tuples,
            transfer_cb=transfer_cb,
            metadata=metadata,
        )

    def upload(
        self, fileobj, name=None, *, transfer_cb=None, metadata=None
    ):
        return self._upload_single(
            "sec/upload/item",
            fileobj,
            name,
            transfer_cb=transfer_cb,
            metadata=metadata,
        )

    def upload_multiple_via_source(
        self, source, file_and_name_tuples, *, transfer_cb=None, metadata=None
    ):
        return self._upload_multiple(
            f"open/upload/item/{source}",
            file_and_name_tuples,
            transfer_cb=transfer_cb,
            metadata=metadata,
        )

    def upload_via_source(
        self, source, fileobj, name=None, *, transfer_cb=None, metadata=None
    ):
        return self._upload_single(
            f"open/upload/item/{source}",
            fileobj,
            name,
            transfer_cb=transfer_cb,
            metadata=metadata,
        )

    def _handle_forbidden(self, activity):
        if self.state != APIWrapper.State.LOGGEDIN:
            raise APIWrapper.NotAuthenticated(activity)
        raise APIWrapper.NotAuthorized(activity)

    def check_file_exists(self, sha256sum):
        resp = self._request("GET", f"sec/checkfile/{sha256sum}")
        if resp.status_code == requests.codes.forbidden:
            self._handle_forbidden("Checking for file existence")
        if resp.json().get("exists") is False:
            logger.warning(
                f"Docspell says no file with SHA256 {sha256sum}, "
                "but the the file could exist, see "
                "https://github.com/eikek/docspell/issues/2328"
            )
        return resp.json()

    def get_job_queue(self):
        resp = self._request("GET", "sec/queue/state")
        if resp.status_code == requests.codes.forbidden:
            self._handle_forbidden("Getting the job queue")
        return resp.json()

    def addon_update(self, addon_id):
        resp = self._request("PUT", f"sec/addon/archive/{addon_id}")
        if resp.status_code == requests.codes.forbidden:
            self._handle_forbidden(f"Updating addon {addon_id}")
        return resp.json()
