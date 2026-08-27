from unittest.mock import MagicMock, patch

import pytest

from jobflow.ingestion.email_client import (
    ImapConnectionError,
    ImapJobEmailClient,
    _build_imap_search,
    _friendly_imap_error,
    _quote_mailbox,
)


def test_quote_mailbox_with_spaces():
    assert _quote_mailbox("[Gmail]/All Mail") == '"[Gmail]/All Mail"'
    assert _quote_mailbox("INBOX") == '"INBOX"'


def test_build_imap_search_with_single_date():
    from datetime import date

    criteria = _build_imap_search(
        unseen_only=False,
        source_filter="linkedin",
        date_from=date(2024, 8, 15),
        date_to=date(2024, 8, 15),
    )
    assert criteria == '(FROM "linkedin" SINCE 15-Aug-2024 BEFORE 16-Aug-2024)'


def test_build_imap_search_with_date_range():
    from datetime import date

    criteria = _build_imap_search(
        unseen_only=True,
        source_filter="all",
        date_from=date(2024, 8, 1),
        date_to=date(2024, 8, 31),
    )
    assert criteria == '(UNSEEN SINCE 01-Aug-2024 BEFORE 01-Sep-2024)'


def test_friendly_gmail_app_password_error():
    exc = _friendly_imap_error(Exception("Application-specific password required"))
    assert "App Password" in str(exc)
    assert exc.hint is not None


@patch("jobflow.ingestion.email_client.get_settings")
def test_fetch_quotes_gmail_all_mail_folder(mock_settings):
    settings = MagicMock()
    settings.imap_user = "user@gmail.com"
    settings.imap_password = "app-password"
    settings.imap_host = "imap.gmail.com"
    settings.imap_port = 993
    settings.imap_use_ssl = True
    settings.imap_folder = "[Gmail]/All Mail"
    settings.imap_fetch_limit = 50
    settings.imap_linkedin_fetch_limit = 500
    settings.imap_job_senders_list = []
    settings.imap_subject_keywords_list = []
    settings.imap_mark_read = True
    mock_settings.return_value = settings

    with patch("jobflow.ingestion.email_client.imaplib.IMAP4_SSL") as mock_imap:
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b""])

        client = ImapJobEmailClient()
        client.fetch_job_emails()

        mock_conn.select.assert_called_once_with('"[Gmail]/All Mail"')


@patch("jobflow.ingestion.email_client.get_settings")
def test_fetch_raises_friendly_error_on_auth_failure(mock_settings):
    settings = MagicMock()
    settings.imap_user = "user@gmail.com"
    settings.imap_password = "wrong"
    settings.imap_host = "imap.gmail.com"
    settings.imap_port = 993
    settings.imap_use_ssl = True
    settings.imap_folder = "INBOX"
    settings.imap_fetch_limit = 50
    settings.imap_job_senders_list = []
    settings.imap_subject_keywords_list = []
    settings.imap_mark_read = True
    mock_settings.return_value = settings

    import imaplib

    with patch("jobflow.ingestion.email_client.imaplib.IMAP4_SSL") as mock_imap:
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.login.side_effect = imaplib.IMAP4.error(
            b"[ALERT] Application-specific password required (Failure)"
        )
        client = ImapJobEmailClient()
        with pytest.raises(ImapConnectionError) as err:
            client.fetch_job_emails()
        assert "App Password" in str(err.value)
