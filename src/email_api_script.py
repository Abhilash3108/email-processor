import base64
# from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import psycopg2
import json
from datetime import datetime, timedelta


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

DB_HOST = 'ENTER_YOUR_DB_HOST_HERE'
DB_NAME = 'ENTER_YOUR_DB_NAME_HERE'
DB_USER = 'ENTER_YOUR_DB_USER_HERE'
DB_PASSWORD = 'ENTER_YOUR_DB_PASSWORD_HERE'


def get_gmail_service():
    flow = InstalledAppFlow.from_client_secrets_file('client_id.json', SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('gmail', 'v1', credentials=creds)
    return service


def fetch_and_store_emails(service, cursor):
    messages_list = service.users().messages().list(userId='me').execute()
    messages = messages_list.get('messages', [])

    for message in messages:
        email_details = service.users().messages().get(
            userId='me',
            id=message['id']
        ).execute()
        message_id = email_details['id']
        subject = get_header(email_details, 'Subject')
        sender_email = get_header(email_details, 'From')
        recipient_email = get_header(email_details, 'To')
        received_datetime = get_received_datetime(email_details)
        body = get_body(email_details)
        is_read = 'UNREAD' not in email_details['labelIds']

        store_email_in_database(
            cursor,
            message_id,
            subject,
            sender_email,
            recipient_email,
            received_datetime,
            body,
            is_read
        )


def get_header(email_details, header_name):
    headers = email_details['payload']['headers']
    for header in headers:
        if header['name'] == header_name:
            return header['value']
    return None


def get_received_datetime(email_details):
    return datetime.fromtimestamp(int(email_details['internalDate']) / 1000.0)


def get_body(email_details):
    if 'parts' in email_details['payload']:
        return base64.urlsafe_b64decode(
            email_details['payload']['parts'][0]['body']['data']
        ).decode('utf-8')
    else:
        return base64.urlsafe_b64decode(
            email_details['payload']['body']['data']
        ).decode('utf-8')


def store_email_in_database(
    cursor,
    message_id,
    subject,
    sender_email,
    recipient_email,
    received_datetime,
    body,
    is_read
):
    cursor.execute("""
        INSERT INTO emails (
            message_id,
            subject,
            sender_email,
            recipient_email,
            received_datetime,
            body,
            is_read)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (message_id, subject, sender_email, recipient_email, received_datetime, body, is_read)
    )


def apply_rules_and_actions(rules, cursor, service):
    cursor.execute("SELECT * FROM emails")
    emails = cursor.fetchall()

    for email in emails:
        for rule in rules:
            if check_rule_conditions(email, rule):
                execute_actions(email, rule, service)


def check_rule_conditions(email, rule):
    conditions = rule.get('conditions', [])
    if rule.get('predicate') == 'All':
        return all(check_condition(email, condition) for condition in conditions)
    elif rule.get('predicate') == 'Any':
        return any(check_condition(email, condition) for condition in conditions)
    return False


def check_condition(email, condition):
    field_name = condition['field_name']
    predicate = condition['predicate']
    value = condition['value']

    if field_name == 'Received':
        received_date = datetime.strptime(email[4], '%Y-%m-%d %H:%M:%S')
        if predicate == 'Less than' and received_date < (datetime.now() - timedelta(days=value)):
            return True
        elif predicate == 'Greater than' and received_date > (datetime.now() - timedelta(days=value)):
            return True
        else:
            return False
    elif predicate == 'Contains' and value in email[field_name]:
        return True
    elif predicate == 'Does not Contain' and value not in email[field_name]:
        return True
    elif predicate == 'Equals' and email[field_name] == value:
        return True
    elif predicate == 'Does not equal' and email[field_name] != value:
        return True
    return False


def execute_actions(email, rule, service):
    actions = rule.get('actions', [])
    for action in actions:
        if action == 'Mark as read':
            mark_email_as_read(email[1], service)
        elif action == 'Mark as unread':
            mark_email_as_unread(email[1], service)
        elif action == 'Move Message':
            move_email_to_folder(email[1], rule.get('folder'), service)


def mark_email_as_read(email_id, service):
    service.users().messages().modify(userId='me', id=email_id, body={'removeLabelIds': ['READ']}).execute()


def mark_email_as_unread(email_id, service):
    service.users().messages().modify(userId='me', id=email_id, body={'addLabelIds': ['UNREAD']}).execute()


def move_email_to_folder(email_id, folder_name, service):
    user_id = 'me'
    label_id = create_label(folder_name, service)
    service.users().messages().modify(userId=user_id, id=email_id, body={'addLabelIds': [label_id]}).execute()


def create_label(label_name, service):
    label = {'name': label_name}
    label = service.users().labels().create(userId='me', body=label).execute()
    return label['id']


def main():
    service = get_gmail_service()

    connection = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = connection.cursor()

    # create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id SERIAL PRIMARY KEY,
            message_id VARCHAR(255) UNIQUE,
            subject VARCHAR(255),
            sender_email VARCHAR(255),
            recipient_email VARCHAR(255),
            received_datetime TIMESTAMP,
            body TEXT,
            is_read BOOLEAN
        )
    ''')

    fetch_and_store_emails(service)

    with open('rules.json') as json_file:
        rules = json.load(json_file)
    apply_rules_and_actions(rules, cursor)

    connection.commit()
    cursor.close()
    connection.close()


if __name__ == '__main__':
    main()
