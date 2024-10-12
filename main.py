
import copy
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Response, responses
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport import requests
from google.oauth2 import id_token

import session
from dependencies import require_user, valid_note
from models import GoogleUser, Note, NoteOut, User
from session import notes, users

app = FastAPI(
    servers=[
        {"url": "https://api.nerine.dev"},
        {"url": "http://localhost:8000"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.get("/", response_description="Redirects to /docs")
async def docs_redirect() -> responses.RedirectResponse:
    return responses.RedirectResponse(url="/docs")


@app.get("/login")
async def login(google_token: str, response: Response) -> User:
    details_raw: dict = id_token.verify_oauth2_token(  # type: ignore
        google_token, requests.Request(), session.google_client_id)
    details = GoogleUser.model_validate(details_raw)
    try:
        user = next(u for u in users if u.google_id == details.sub)
    except StopIteration:
        user = User(
            google_id=details.sub,
        )
        users.append(user)
    response.set_cookie(key="user_id", value=str(user.id))
    return user


@app.get("/note", response_model=list[NoteOut])
async def get_notes(user: Annotated[User, Depends(require_user)]) -> list[Note]:
    ret_notes = copy.deepcopy(notes)
    # Rewrite password if enctrypted
    for note in ret_notes:
        if note.creator_id != user.id:
            ret_notes.remove(note)
        if note.is_encrypted:
            note.note = "encrypted"
    return ret_notes


@app.post("/note", response_model=NoteOut)
async def create_note(
        name: str,
        note: str,
        user: Annotated[User, Depends(require_user)],
        password: str | None = None,
) -> Note:
    new_note = Note(
        note=note,
        password=password,
        name=name,
        is_encrypted=password is not None and password != "",
        creator_id=user.id,
    )
    notes.append(new_note)
    return new_note


@app.get("/note/{note_id}")
async def get_note(note: Annotated[Note, Depends(valid_note)]) -> Note:
    return note

if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=8000)  # noqa: S104