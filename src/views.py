from rest_framework.decorators import api_view
from rest_framework.response import Response
from src.email_api_script import (
    get_gmail_service,
    mark_email_as_read,
    mark_email_as_unread,
    move_email_to_folder
)

from pydantic import BaseModel


class MarkAsReadRequest(BaseModel):
    email_id: str


class MarkAsUnreadRequest(BaseModel):
    email_id: str


class MoveEmailRequest(BaseModel):
    email_id: str
    folder_name: str


service = get_gmail_service()


@api_view(['POST'])
def mark_as_read(request: MarkAsReadRequest):
    try:
        email_id = request.data.get('email_id')
        mark_email_as_read(email_id, service)
        return Response({'status': 'success'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})


@api_view(['POST'])
def mark_as_unread(request: MarkAsUnreadRequest):
    try:
        email_id = request.data.get('email_id')
        mark_email_as_unread(email_id, service)
        return Response({'status': 'success'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})


@api_view(['POST'])
def move_email(request: MoveEmailRequest):
    try:
        email_id = request.data.get('email_id')
        folder_name = request.data.get('folder_name')
        move_email_to_folder(email_id, folder_name, service)
        return Response({'status': 'success'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})