import pytest
from expecter import expect
import requests_mock
import functools
import os
import re
import json
from io import BytesIO
from collections import OrderedDict
import hashlib
from operator import itemgetter
import datetime

from pydocspell import APIWrapper

MOCK_SESSION_KEY = "thiemaequaethohsah4ahfooMu0ATo4P"
MOCK_ANYTHING = "_MOCK_MATCHES_ANYTHING"
MOCK_BASEURL = "http://docspell.example.org"

BASEURL = os.getenv("DOCSPELL_BASEURL", MOCK_BASEURL)
I_AM_BEING_MOCKED = BASEURL == MOCK_BASEURL


def mock_me(
    method,
    endpoint,
    *,
    apiurl=None,
    params=None,
    returns=None,
    returns_fn=None,
):
    returns = returns or {}

    if not callable(returns_fn):
        returns_fn = json.dumps

    params = params or {}
    if not I_AM_BEING_MOCKED and "token" in returns:
        returns["token"] = MOCK_ANYTHING

    def proxy(fn, *args, **kwargs):
        @pytest.mark.parametrize(("params", "returns"), ((params, returns),))
        @functools.wraps(fn)
        def inner(params, returns, *args, **kwargs):
            if I_AM_BEING_MOCKED:
                with requests_mock.Mocker() as mocker:
                    mocker.request(
                        method,
                        APIWrapper.make_endpoint_url(
                            BASEURL, endpoint, apiurl=apiurl
                        ).format(**(params or {})),
                        text=returns_fn(returns),
                    )
                    return fn(params, returns, *args, **kwargs)
            else:
                return fn(params, returns, *args, **kwargs)

        return inner

    return proxy


CREDENTIALS = OrderedDict(
    collective=os.getenv("DOCSPELL_COLLECTIVE", "test"),
    username=os.getenv("DOCSPELL_USERNAME", "test"),
    password=os.getenv("DOCSPELL_PASSWORD", "test"),
)


@pytest.fixture
def api():
    return APIWrapper(BASEURL)


@pytest.fixture
def authenticated_api(api):
    if I_AM_BEING_MOCKED:
        # We need to fake the @mock_me decorator because it does
        # not actually work a fixture
        returns = {
            "collective": CREDENTIALS["collective"],
            "user": CREDENTIALS["username"],
            "success": True,
            "message": "Login successful",
            "token": MOCK_SESSION_KEY,
        }
        proxy = mock_me("POST", "open/auth/login", returns=returns)

        @functools.wraps(api.login)
        def login_proxy(params, returns, *args):
            # lose (params, returns)
            return api.login(*args)

        inner = proxy(login_proxy)
        resp = inner({}, returns, *CREDENTIALS.values())
        return api, resp
    else:
        resp = api.login(*CREDENTIALS.values())
        return api, resp


@pytest.mark.construct
def describe_constructor():
    def with_default_args(api):
        version = 1
        expect(api.baseurl) == BASEURL
        expect(api.apiurl) == BASEURL + APIWrapper.DEFAULT_API_PATH.format(
            version=version
        )
        expect(api.version) == version
        expect(api.state) == api.State.INIT

    def with_version_arg():
        ver = 5
        api = APIWrapper(BASEURL, version=ver)
        expect(api.version) == ver

    def with_api_version_in_url(caplog):
        baseurl = f"{BASEURL}/api/v2"
        api = APIWrapper(baseurl)
        expect(caplog.records[0].message).contains("/api/")
        expect(caplog.records[0].levelname) == "WARNING"
        caplog.clear()
        expect(api.baseurl) == baseurl.split("/api")[0]
        expect(api.apiurl) == baseurl
        expect(api.version) == 2


@pytest.mark.context
def describe_context_manager():
    def state_representation():
        with APIWrapper(BASEURL) as wrapper:
            assert wrapper.state == APIWrapper.State.INIT

        assert wrapper.state == APIWrapper.State.SHUTDOWN


@pytest.mark.util
def describe_making_urls():
    def apiurl_without_version():
        url = APIWrapper.make_api_url(BASEURL)
        expect(url) == f"{BASEURL}/api/v{APIWrapper.DEFAULT_VERSION}"

    def apiurl_with_version():
        url = APIWrapper.make_api_url(BASEURL, version=2)
        expect(url) == f"{BASEURL}/api/v2"

    def with_default_apiurl():
        endpoint = "foo"
        url = APIWrapper.make_endpoint_url(BASEURL, endpoint)
        expect(url) == f"{APIWrapper.make_api_url(BASEURL)}/{endpoint}"

    def overriding_apiurl():
        endpoint = "foo"
        url = APIWrapper.make_endpoint_url(BASEURL, endpoint, apiurl=BASEURL)
        expect(url) == f"{BASEURL}/{endpoint}"


@pytest.mark.api_generic
def describe_open_api():
    @mock_me(
        "GET",
        "api/info/version",
        apiurl=BASEURL,
        returns={"version": "0.40.0"},
    )
    def get_docspell_version(params, returns, api):
        expect(api.get_docspell_version().get("version")) == returns["version"]

@pytest.mark.api_generic
def describe_error_handling():
    @mock_me(
        "GET",
        "api/info/version",
        apiurl=BASEURL,
        returns_fn=lambda s: "",
    )
    def when_empty_response_received(
        params, returns, api
    ):
        with pytest.raises(APIWrapper.EmptyResponse):
            api.get_docspell_version().get("version")


@pytest.mark.api_auth
def describe_api_auth():
    @mock_me(
        "POST",
        "open/auth/login",
        returns={
            "collective": CREDENTIALS["collective"],
            "user": CREDENTIALS["username"],
            "success": True,
            "message": "Login successful",
            "token": MOCK_SESSION_KEY,
        },
    )
    def login(params, returns, api):
        ret = api.login(**CREDENTIALS)
        for k, v in returns.items():
            if v == MOCK_ANYTHING:
                continue
            expect(ret[k]) == v
        expect(api.state) == APIWrapper.State.LOGGEDIN

    @mock_me("POST", "sec/auth/logout")
    def logout(params, returns, authenticated_api):
        api, _ = authenticated_api
        ret = api.logout()
        expect(api.state) == APIWrapper.State.LOGGEDOUT
        expect(ret) == {}


@pytest.mark.api_files
def describe_api_upload():
    ONEPIXELFILE = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9bU\x00\x00\x01\"iCCPICC profile\x00\x00(\x91\x9d\x90\xb1J\xc3P\x14\x86\xbfTQ):Y\x1cD0\x83\x83KG39X\x15\x82P!\xc6\nV\xa74I\xb1\x98\xc4\x90\xa4\x14\xdf\xc07\xd1\x87\xe9 \x08\xbe\x82\xbb\x82\xb3\xff\x8d\x0e\x0ef\xf1\x86\xc3\xffq8\xe7\xff\xef\r\xb4\xec$L\xcb\xc5\x03H\xb3\xaap\xfd\xde\xf0rxe/\xbf\xd1\xa6\xa3o\x97\xed ,\xf3\x9e\xe7\xf5i<\x9f\xafXF_\xba\xc6\xaby\xee\xcf\xb3\x14\xc5e(\x9d\xab\xb20/*\xb0\xf6\xc5\xce\xac\xca\r\xab\xe8\xdc\x0e\xfc#\xf1\x83\xd8\x8e\xd2,\x12?\x89w\xa242lv\xfd4\x99\x86?\x9e\xe66\xabqvqn\xfa\xaa-\\N8\xc5\xc3f\xc4\x94\t\t\x15]i\xa6\xce1\x0e{R\x97\x82\x80{JBiB\xac\xdeL3\x157\xa2RN.\x87\xa2\x81H\xb7i\xc8\xdb\xac\xf3<\xa5\x8c\xe41\x91\x97I\xb8#\x95\xa7\xc9\xc3\xfc\xdf\xef\xb5\x8f\xb3z\xd3\xda\x98\xe7A\x11\xd4\xad\x05Uk<\x86\xf7GX\x1b\xc2\xfa3\xb4\xaf\x1b\xb2V~\xbf\xada\xc6\xa9g\xfe\xf9\xc6/@VP\x90\xbd\x89wI\x00\x00\x00\tpHYs\x00\x00\x00'\x00\x00\x00'\x01*\t\x91O\x00\x00\x00\x07tIME\x07\xe7\n\x14\x14(;\xa5'\x15\xd1\x00\x00\x00\nIDAT\x08\xd7c\xf8\x0f\x00\x01\x01\x01\x00\x1b\xb6\xeeV\x00\x00\x00\x00IEND\xaeB`\x82"  # noqa:E501
    ONEPIXELFILE_SHA256SUM = hashlib.sha256(ONEPIXELFILE).hexdigest()

    @pytest.fixture
    def onepixelfile():
        return BytesIO(ONEPIXELFILE)

    def single_via_source(monkeypatch, api, onepixelfile):
        def monkey_upload(
            endpoint, files, name=None, *, transfer_cb=None, metadata=None
        ):
            return files[0]

        with monkeypatch.context() as m:
            m.setattr(api, "_upload_multiple", monkey_upload)
            fnt = (onepixelfile, "motd")
            resp = api.upload_via_source("source", *fnt)
            assert resp == fnt

    @mock_me(
        "POST",
        "open/upload/item/{source}",
        params={"source": "BL7Kt1wxjpC-xgu8vG8YVbN-6vxwdRdR9Fw-ZEdYG96UTU4"},
        returns={"success": True, "message": "Files submitted."},
    )
    def multiple_via_source(params, returns, authenticated_api, onepixelfile):
        api, _ = authenticated_api
        files = [(onepixelfile, "one"), (onepixelfile, "two")]
        resp = api.upload_multiple_via_source(params["source"], files)
        expect(resp["success"]) is returns["success"]
        expect(resp["message"]) == returns["message"]

    def when_nonfile_provided(api):
        with pytest.raises(ValueError):
            api.upload_via_source("source", "string")

    def when_closed_file_provided(api):
        with open(os.devnull, "rb") as f:
            pass
        with pytest.raises(ValueError):
            api.upload_via_source("source", f)

    @mock_me(
        "GET",
        "sec/checkfile/{sha256sum}",
        params={"sha256sum": ONEPIXELFILE_SHA256SUM},
        returns={
            "exists": True,
            "items": [
                {
                    "id": MOCK_ANYTHING,
                    "name": "one",
                    "direction": "incoming",
                    "state": "created",
                    "created": MOCK_ANYTHING,
                    "itemDate": None,
                },
                {
                    "id": MOCK_ANYTHING,
                    "name": "two",
                    "direction": "incoming",
                    "state": "created",
                    "created": MOCK_ANYTHING,
                    "itemDate": None,
                },
            ],
        },
    )
    def check_if_file_exists(params, returns, authenticated_api, onepixelfile):
        api, _ = authenticated_api
        resp = api.check_file_exists(params["sha256sum"])
        expect(resp["exists"]) is returns["exists"]
        for inp, out in zip(
            sorted(returns["items"], key=itemgetter("name")),
            sorted(
                sorted(resp["items"], key=itemgetter("name")),
                key=itemgetter("created"),
            ),
        ):
            for k, v in inp.items():
                if v == MOCK_ANYTHING:
                    expect(k in out) is True
                else:
                    expect(inp[k]) == out[k]

    @mock_me(
        "GET",
        "sec/checkfile/{sha256sum}",
        params={
            "sha256sum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # noqa:E501
        },
        returns={"exists": False, "items": []},
    )
    def check_if_file_not_exists(
        params, returns, authenticated_api, onepixelfile, caplog
    ):
        api, _ = authenticated_api
        resp = api.check_file_exists(params["sha256sum"])
        for rec in caplog.records:
            if (
                "docspell/issues/2328" in rec.message
                and rec.levelname == "WARNING"
            ):
                break
        else:
            raise AssertionError("No warning about issue 2328 was logged")
        caplog.clear()
        expect(resp["exists"]) is returns["exists"]
        expect(resp["items"]) == returns["items"]

    @mock_me(
        "GET",
        "sec/queue/state",
    )
    def check_getting_the_job_queue(params, returns, authenticated_api):
        api, _ = authenticated_api
        resp = api.get_job_queue()

    def single_authenticated(monkeypatch, api, onepixelfile):
        def monkey_upload(
            endpoint, files, name=None, *, transfer_cb=None, metadata=None
        ):
            return files[0]

        with monkeypatch.context() as m:
            m.setattr(api, "_upload_multiple", monkey_upload)
            fnt = (onepixelfile, "motd")
            resp = api.upload(*fnt)
            assert resp == fnt

    @mock_me(
        "POST",
        "sec/upload/item",
        returns={"success": True, "message": "Files submitted."},
    )
    def multiple_authenticated(
        params, returns, authenticated_api, onepixelfile
    ):
        api, _ = authenticated_api
        files = [(onepixelfile, "one"), (onepixelfile, "two")]
        resp = api.upload_multiple(files)
        expect(resp["success"]) is returns["success"]


@pytest.mark.api_metadata
def describe_api_metadata():
    @mock_me(
        "PUT",
        "sec/item/{id}/date",
        params={"id": "7DRnuarqeVc-9QTFof7pocU-VSsreZ2k5oh-zebbFYMnwRQ"},
        returns={"success": True, "message": "Item date updated."},
    )
    def set_item_date(params, returns, authenticated_api):
        api, _ = authenticated_api
        date = datetime.date(1970, 1, 1)
        resp = api.set_item_date(params["id"], date)
        expect(resp["success"]) is returns["success"]

    @mock_me(
        "POST",
        "sec/item/{id}/confirm",
        params={"id": "7DRnuarqeVc-9QTFof7pocU-VSsreZ2k5oh-zebbFYMnwRQ"},
        returns={"success": True, "message": "Item data confirmed"},
    )
    def confirm_item(params, returns, authenticated_api):
        api, _ = authenticated_api
        resp = api.confirm_item(params["id"])
        expect(resp["success"]) is returns["success"]

    @mock_me(
        "POST",
        "sec/item/{id}/unconfirm",
        params={"id": "7DRnuarqeVc-9QTFof7pocU-VSsreZ2k5oh-zebbFYMnwRQ"},
        returns={"success": True, "message": "Item back to created"},
    )
    def unconfirm_item(params, returns, authenticated_api):
        api, _ = authenticated_api
        resp = api.unconfirm_item(params["id"])
        expect(resp["success"]) is returns["success"]

    @mock_me(
        "POST",
        "sec/item/{id}/unconfirm",
        params={"id": "7DRnuarqeVc-9QTFof7pocU-VSsreZ2k5oh-zebbFYMnwRQ"},
        returns={"success": True, "message": "Item back to created"},
    )
    def unconfirm_item_arg(params, returns, authenticated_api):
        api, _ = authenticated_api
        resp = api.confirm_item(params["id"], confirm=False)
        expect(resp["success"]) is returns["success"]


@pytest.mark.api_addons
def describe_api_addons():
    @mock_me(
        "PUT",
        "sec/addon/archive/{id}",
        params={"id": "89uniB21tj9-HwWaVk3gsvW-87FpJ9dGWS6-Kw9DQnvDr3W"},
        returns={"success": True, "message": "Addon updated in background"},
    )
    def addon_update(params, returns, authenticated_api):
        api, _ = authenticated_api
        resp = api.addon_update(params["id"])
        expect(resp["success"]) is returns["success"]
        expect(resp["message"]) is returns["message"]

    @mock_me(
        "PUT",
        "sec/addon/archive/{id}",
        params={"id": "89uniB21tj9-HwWaVk3gsvW-87FpJ9dGWS6-Kw9DQnvDr3W"},
        returns={"success": True, "message": r"Addon updated: .+"},
    )
    def addon_update_sync(params, returns, authenticated_api):
        api, _ = authenticated_api
        resp = api.addon_update(params["id"], sync=True)
        expect(resp["success"]) is returns["success"]
        expect(re.match(returns["message"], resp["message"])) is not None
