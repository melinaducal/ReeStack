from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Friendship, User
from app.models.friendship import (
    FRIENDSHIP_ACCEPTED,
    FRIENDSHIP_PENDING,
    FRIENDSHIP_REJECTED,
)
from app.models.notification import (
    NOTIFICATION_FRIEND_ACCEPTED,
    NOTIFICATION_FRIEND_REQUEST,
)
from app.schemas import (
    FriendRequestResponse,
    FriendResponse,
    FriendshipStatusResponse,
)
from app.services.notifications import create_notification

router = APIRouter(prefix="/friends", tags=["friends"])

ALREADY_FRIENDS = "Ya son amigos"
ALREADY_REQUESTED = "Ya enviaste una solicitud de amistad"
ALREADY_ANSWERED = "La solicitud ya fue respondida"
CONFLICT_DETAIL = (
    "La relación de amistad cambió mientras se procesaba la solicitud. "
    "Volvé a intentarlo."
)


def _pair_filter(first_id: int, second_id: int):
    return or_(
        (Friendship.requester_id == first_id)
        & (Friendship.addressee_id == second_id),
        (Friendship.requester_id == second_id)
        & (Friendship.addressee_id == first_id),
    )


def _find_pair(
    db: Session, first_id: int, second_id: int
) -> Optional[Friendship]:
    return db.query(Friendship).filter(_pair_filter(first_id, second_id)).first()


def _other_user(friendship: Friendship, viewer_id: int) -> User:
    if friendship.requester_id == viewer_id:
        return friendship.addressee
    return friendship.requester


def _request_payload(friendship: Friendship, viewer_id: int) -> dict:
    return {
        "friendship_id": friendship.id,
        "user": _other_user(friendship, viewer_id),
        "created_at": friendship.created_at,
        "direction": "outgoing" if friendship.requester_id == viewer_id else "incoming",
    }


def _status_payload(friendship: Friendship, viewer_id: int) -> dict:
    if friendship.status == FRIENDSHIP_ACCEPTED:
        value = "friends"
    elif friendship.status == FRIENDSHIP_PENDING:
        value = (
            "pending_outgoing"
            if friendship.requester_id == viewer_id
            else "pending_incoming"
        )
    else:
        value = "rejected"
    return {"status": value, "friendship_id": friendship.id}


def _accept_pending(db: Session, friendship: Friendship, current_user: User) -> dict:
    """Accept a pending request with a conditional UPDATE.

    The filter includes ``status == pending`` so two concurrent accepts can
    never both succeed: only the request that changes the row creates the
    ``friend_accepted`` notification.
    """
    updated = (
        db.query(Friendship)
        .filter(
            Friendship.id == friendship.id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == FRIENDSHIP_PENDING,
        )
        .update(
            {
                Friendship.status: FRIENDSHIP_ACCEPTED,
                Friendship.responded_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    if not updated:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_ANSWERED
        )

    create_notification(
        db,
        recipient_id=friendship.requester_id,
        actor_id=current_user.id,
        type=NOTIFICATION_FRIEND_ACCEPTED,
    )
    db.commit()
    db.refresh(friendship)
    return _status_payload(friendship, current_user.id)


def _send_or_resolve(
    db: Session, current_user: User, target: User
) -> dict:
    friendship = _find_pair(db, current_user.id, target.id)

    if friendship and friendship.status == FRIENDSHIP_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_FRIENDS
        )

    if friendship and friendship.status == FRIENDSHIP_PENDING:
        if friendship.addressee_id == current_user.id:
            # The other user already asked first: sending a request back
            # accepts it instead of creating a mirrored row.
            return _accept_pending(db, friendship, current_user)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_REQUESTED
        )

    if friendship:
        # A rejected row is reused so the unique pair constraint still holds.
        friendship.requester_id = current_user.id
        friendship.addressee_id = target.id
        friendship.status = FRIENDSHIP_PENDING
        friendship.created_at = datetime.utcnow()
        friendship.responded_at = None
    else:
        friendship = Friendship(
            requester_id=current_user.id,
            addressee_id=target.id,
            status=FRIENDSHIP_PENDING,
        )
        db.add(friendship)

    # flush() surfaces a duplicate race before the notification is queued.
    db.flush()
    create_notification(
        db,
        recipient_id=target.id,
        actor_id=current_user.id,
        type=NOTIFICATION_FRIEND_REQUEST,
    )
    db.commit()
    db.refresh(friendship)
    return _status_payload(friendship, current_user.id)


def _resolve_after_conflict(
    db: Session, current_user: User, target: User
) -> dict:
    """Resolve the pair after another transaction won the insert race."""
    for _ in range(3):
        friendship = _find_pair(db, current_user.id, target.id)
        if friendship is None:
            return _send_or_resolve(db, current_user, target)
        if friendship.status == FRIENDSHIP_ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_FRIENDS
            )
        if friendship.status == FRIENDSHIP_PENDING:
            if friendship.addressee_id == current_user.id:
                return _accept_pending(db, friendship, current_user)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_REQUESTED
            )
        # The concurrent row was rejected: reuse it through the normal path.
        return _send_or_resolve(db, current_user, target)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=CONFLICT_DETAIL
    )


@router.get("", response_model=List[FriendResponse])
@router.get("/", response_model=List[FriendResponse], include_in_schema=False)
def list_friends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendships = (
        db.query(Friendship)
        .filter(
            Friendship.status == FRIENDSHIP_ACCEPTED,
            or_(
                Friendship.requester_id == current_user.id,
                Friendship.addressee_id == current_user.id,
            ),
        )
        .all()
    )
    return [
        {
            "friendship_id": friendship.id,
            "user": _other_user(friendship, current_user.id),
            "since": friendship.responded_at or friendship.created_at,
        }
        for friendship in friendships
    ]


@router.get("/requests", response_model=List[FriendRequestResponse])
def list_incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendships = (
        db.query(Friendship)
        .filter(
            Friendship.status == FRIENDSHIP_PENDING,
            Friendship.addressee_id == current_user.id,
        )
        .order_by(Friendship.id.desc())
        .all()
    )
    return [_request_payload(friendship, current_user.id) for friendship in friendships]


@router.get("/requests/sent", response_model=List[FriendRequestResponse])
def list_sent_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendships = (
        db.query(Friendship)
        .filter(
            Friendship.status == FRIENDSHIP_PENDING,
            Friendship.requester_id == current_user.id,
        )
        .order_by(Friendship.id.desc())
        .all()
    )
    return [_request_payload(friendship, current_user.id) for friendship in friendships]


@router.get("/status/{user_id}", response_model=FriendshipStatusResponse)
def get_friendship_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        return {"status": "self", "friendship_id": None}
    friendship = _find_pair(db, current_user.id, user_id)
    if not friendship:
        return {"status": "none", "friendship_id": None}
    return _status_payload(friendship, current_user.id)


@router.post("/requests/{user_id}", response_model=FriendshipStatusResponse)
def send_friend_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podés enviarte una solicitud a vos mismo",
        )

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        return _send_or_resolve(db, current_user, target)
    except IntegrityError:
        # Another request for the same pair was committed between our SELECT
        # and our INSERT. Roll back (which also discards the queued
        # notification) and resolve against the row that won the race.
        db.rollback()
        try:
            return _resolve_after_conflict(db, current_user, target)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=CONFLICT_DETAIL
            )


@router.post("/requests/{request_id}/accept", response_model=FriendshipStatusResponse)
def accept_friend_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendship = db.query(Friendship).filter(Friendship.id == request_id).first()
    if not friendship:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if friendship.addressee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para responder esta solicitud",
        )
    if friendship.status != FRIENDSHIP_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_ANSWERED
        )

    try:
        return _accept_pending(db, friendship, current_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=CONFLICT_DETAIL
        )


@router.post("/requests/{request_id}/reject", response_model=FriendshipStatusResponse)
def reject_friend_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendship = db.query(Friendship).filter(Friendship.id == request_id).first()
    if not friendship:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if friendship.addressee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para responder esta solicitud",
        )
    if friendship.status != FRIENDSHIP_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_ANSWERED
        )

    updated = (
        db.query(Friendship)
        .filter(
            Friendship.id == friendship.id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == FRIENDSHIP_PENDING,
        )
        .update(
            {
                Friendship.status: FRIENDSHIP_REJECTED,
                Friendship.responded_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    if not updated:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ALREADY_ANSWERED
        )

    db.commit()
    db.refresh(friendship)
    return _status_payload(friendship, current_user.id)


@router.delete("/{user_id}")
def remove_friend(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.status == FRIENDSHIP_ACCEPTED,
            _pair_filter(current_user.id, user_id),
        )
        .first()
    )
    if not friendship:
        raise HTTPException(status_code=404, detail="No son amigos")

    try:
        deleted = (
            db.query(Friendship)
            .filter(Friendship.id == friendship.id)
            .delete(synchronize_session=False)
        )
        if not deleted:
            db.rollback()
            raise HTTPException(status_code=404, detail="No son amigos")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=CONFLICT_DETAIL
        )

    return {"message": "Amistad eliminada", "user_id": user_id}
