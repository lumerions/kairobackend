from fastapi import APIRouter,Request,Cookie,Depends,UploadFile,File,Path
from routes.shared.shared import userlimiter
from lib.getPostgresConn import *
from middleware.authMiddleware import sessionValid
from middleware.csrfMiddleware import CheckCSRFToken
from lib.schemas import groupCreate,groupDescription,groupName,groupShout,groupJoin,groupFunds
from lib.serializer import serializer
from lib.functions import returnSerializedCookieData
import math

router = APIRouter(
    prefix="/api/groups",
    tags=["forums"]
)

@router.get("/{group_id}")
@userlimiter.limit("70/minute")
async def getgroupdata(request : Request,group_id: int = Path(...),Session : str = Cookie(None)):
    pgPool = await getpgPool()

    async with pgPool.acquire() as conn:
        GroupData = await conn.fetchrow("""
            SELECT g.name, g.description, g.groupshout, g.groupcreator_id, g.groupshout, i.filename
            FROM groups g
            LEFT JOIN group_images i ON i.group_id = g.id
            WHERE g.id = $1
        """, group_id)

    return GroupData

@router.get("/auditlog/{group_id}")
@userlimiter.limit("70/minute")
async def getgroupdata(request : Request,group_id: int = Path(...),Session : str = Cookie(None),page : int = 1):
    pgPool = await getpgPool()
    Limit = 100
    offset = (page - 1) * Limit

    async with pgPool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                gal.group_id,
                gal.audit_user_id,
                u.username,
                gal.audit_log_text,
                gal.created_at,
                COUNT(*) OVER() AS total_count
            FROM group_audit_log gal
            JOIN users u 
                ON u.id = gal.audit_user_id
            WHERE gal.group_id = $1
            ORDER BY gal.created_at DESC
            LIMIT $2
            OFFSET $3;
        """, group_id,Limit,offset)

    TotalItemCount = rows[0]["total_count"] if rows else 0
    TotalPageCount = math.ceil(TotalItemCount / Limit) if TotalItemCount else 1

    AuditData = [
        {
            "audit_user_id": r["audit_user_id"],
            "audit_log_text": r["audit_log_text"],
            "created_at": r["created_at"]
        }
        for r in rows
    ]

    return {
        "success":True,
        "data": AuditData,
        "currentPage": page,
        "totalPages": TotalPageCount if TotalPageCount else 1,
    }

    
@router.post("/upload/{group_id}",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def creategroup(request : Request,Session : str = Cookie(None),file: UploadFile = File(...),group_id: int = Path(...)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    fileData = await file.read()

    if len(fileData) > 5242880:
        return {"success":False,"message": "File size too big max is 5mb."}

    pgPool = await getpgPool()

    async with pgPool.acquire() as conn:
        await conn.execute("""
            INSERT INTO group_images (group_id, filename, content_type, data)
            VALUES ($1, $2, $3, $4)
        """,
        group_id,
        file.filename,
        file.content_type,
        fileData
        )

    return {"success":True}

@router.post("/create",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def creategroup(request : Request,data : groupCreate,Session : str = Cookie(None),file: UploadFile = File(...)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    fileData = await file.read()

    if len(fileData) > 5242880:
        return {"success":False,"message": "File size too big max is 5mb."}

    GroupName = data.name
    Description = data.description

    if len(GroupName) < 3:
        return {"success":False,"message": "Group name must be atleast 3 characters long."}

    pgPool = await getpgPool()
    UserId = CookieData[0]

    async with pgPool.acquire() as conn:
        GroupId = await conn.fetchval("""
            WITH deducted AS (
                UPDATE balances
                SET robux = robux - 100
                WHERE userid = $1
                AND robux >= 100
                RETURNING userid
            ),
            user_data AS (
                SELECT username, id
                FROM users
                WHERE id = $1
            ),
            new_group AS (
                INSERT INTO groups (
                    description,
                    groupcreator,
                    name,
                    groupcreator_id
                )
                SELECT
                    $2,
                    user_data.username,
                    $3,
                    user_data.id
                FROM deducted
                CROSS JOIN user_data
                RETURNING id
            ),
            user_group AS (
                INSERT INTO group_members (
                    user_id,
                    group_id
                )
                SELECT $1, id
                FROM new_group
            ),
            inserted_group_data AS (
                INSERT INTO additional_group_data (
                    group_id
                )
                SELECT id
                FROM new_group
                RETURNING group_id
            ),
            inserted_image AS (
                INSERT INTO group_images (
                    group_id,
                    filename,
                    content_type,
                    data
                )
                SELECT
                    id,
                    $4,
                    $5,
                    $6
                FROM new_group
                RETURNING group_id
            )
            SELECT group_id
            FROM inserted_image;
        """,
            UserId,
            Description,
            GroupName,
            file.filename,
            file.content_type,
            fileData
        )

        if not GroupId:
            return {"success":False,"message":"Insufficient Funds"}

    return {"success":True,"groupId":GroupId}

@router.post("/changedescription",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changedescription(request : Request,data : groupDescription,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    Description = data.description
    GroupId = data.groupid
    pgPool = await getpgPool()
    Version = CookieData[1]
    UserName = CookieData[2]

    async with pgPool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE groups g
            SET description = $3
            FROM users u
            WHERE g.id = $1
            AND g.groupcreator = $2
            AND u.id = $2
            AND u.version = $4
            RETURNING g.id
        """,
        GroupId,
        UserName,
        Description,
        str(Version)
        )

        if not row:
            return {"success": False, "message": "Not authorized to do this action."}

    return {"success":True}

@router.post("/changegroupshout",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changegroupshout(request : Request,data : groupShout,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    GroupShout = (data.shout or "").strip()
    GroupId = data.groupid
    pgPool = await getpgPool()
    Version = CookieData[1]
    UserName = CookieData[2]

    if len(GroupShout) == 0:
        return {"success":False,"message": "Please provide a valid blurb."}

    async with pgPool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE groups g
            SET groupshout = $3,
                last_groupshout_time = NOW()
            FROM users u
            WHERE g.id = $1
            AND g.groupcreator = $2
            AND u.id = $2
            AND u.version = $4
            RETURNING g.id
        """,
        GroupId,
        UserName,
        GroupShout,
        str(Version)
        )

        if not row:
            return {"success": False, "message": "Not authorized to do this action."}

    return {"success":True}

@router.post("/leavegroup",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def leavegroup(request : Request,data : groupJoin,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    GroupId = data.groupid
    pgPool = await getpgPool()
    UserId = CookieData[0]
    Version = CookieData[1]

    async with pgPool.acquire() as conn:
        row = await conn.fetchrow("""
            DELETE FROM group_members gm
            USING users u
            WHERE gm.group_id = $1
            AND gm.user_id = $2
            AND u.id = $2
            AND u.version = $3
            RETURNING gm.group_id, gm.user_id;
        """,
        GroupId,
        UserId,
        str(Version)
        )

        if not row:
            return {"success": False, "message": "Invalid session or not in group"}

    return {"success":True}

@router.post("/joingroup",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def joingroup(request : Request,data : groupJoin,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    GroupId = data.groupid
    pgPool = await getpgPool()
    UserId = CookieData[0]
    Version = CookieData[1]

    async with pgPool.acquire() as conn:
        row = await conn.fetchrow("""
            WITH valid_user AS (
                SELECT id
                FROM users
                WHERE id = $2
                AND version = $3
            ),
            group_settings AS (
                SELECT manual_approval
                FROM additional_group_data
                WHERE group_id = $1
            )
            INSERT INTO group_members (group_id, user_id, role)
            SELECT
                $1,
                valid_user.id,
                CASE
                    WHEN COALESCE(group_settings.manual_approval, FALSE) THEN 'Guest'
                    ELSE 'Member'
                END
            FROM valid_user
            LEFT JOIN group_settings ON TRUE
            ON CONFLICT DO NOTHING
            RETURNING group_id, user_id, role;
        """,
        GroupId,
        UserId,
        str(Version)
        )

        if not row:
            return {"success": False, "message": "Already in group or invalid session"}

    return {"success":True}

@router.post("/changegroupname",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changegroupname(request : Request,data : groupName,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    NewGroupName = data.name
    GroupId = data.groupid

    if len(NewGroupName) < 3:
        return {"success":False,"message": "Group name must be atleast 3 characters long."}

    pgPool = await getpgPool()
    UserId = CookieData[0]
    Version = CookieData[1]
    UserName = CookieData[2]

    async with pgPool.acquire() as conn:
        UpdatedRow = await conn.fetchrow("""
            WITH valid_user AS (
                SELECT id FROM users WHERE id = $1 AND version = $2
            ),
            deducted AS (
                UPDATE balances
                SET robux = robux - 1000
                WHERE userid = $1
                AND robux >= 1000
                RETURNING userid
            )
            UPDATE groups g
            SET name = $3
            FROM valid_user, deducted
            WHERE g.id = $4
            AND g.groupcreator = $5
            RETURNING g.id
        """,
        UserId,
        str(Version),
        NewGroupName,
        GroupId,
        UserName
        )

        if not UpdatedRow:
            return {"success":True,"message": "Invalid session, not group owner, or not enough robux."}

    return {"success":True}

@router.post("/changegroupowner",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changegroupowner(request : Request,data : groupJoin,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    GroupId = data.groupid
    NewGroupOwnerUsername = data.newgroupownerusername
    pgPool = await getpgPool()
    Version = CookieData[1]
    Username = CookieData[2]

    async with pgPool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE groups g
            SET groupcreator = u2.username,
                groupcreator_id = u2.id
            FROM users u1, users u2
            WHERE g.id = $1
            AND g.groupcreator = u1.username
            AND u1.id = $2
            AND u1.version = $4
            AND u2.username = $3
            RETURNING g.id
        """,
        GroupId,
        Username,
        NewGroupOwnerUsername,
        str(Version)
        )

        if not row:
            return {"success": False, "message": "Not authorized to do this action."}

    return {"success":True}

@router.get("/distributegroupfunds",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def groupfunds(request : Request,data : groupFunds,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    pgPool = await getpgPool()
    GroupId = data.groupid
    RecieverUsername = data.recieverusername
    Amount = data.amount
    UserId = CookieData[0]
    Version = CookieData[1]

    async with pgPool.acquire() as conn:
        updatedRow = await conn.fetchrow("""
            WITH deducted AS (
                UPDATE additional_group_data agd
                SET group_funds = agd.group_funds - $1
                FROM users u1
                WHERE agd.group_id = $2
                AND u1.id = $4
                AND u1.version = $5
                AND agd.group_funds >= $1
                RETURNING agd.group_id
            ),
            credited AS (
                UPDATE balances b
                SET robux = b.robux + $1
                FROM users u2, deducted
                WHERE u2.username = $3
                AND b.userid = u2.id
                RETURNING b.userid
            ),
            inserted AS (
                INSERT INTO group_transactions (
                    group_id,
                    amount,
                    transaction_type
                )
                SELECT
                    $2,
                    $1,
                    'payout'
                FROM credited
                RETURNING group_id
            )
            SELECT * FROM credited;
        """,
            Amount,
            GroupId,
            RecieverUsername,
            UserId,
            str(Version)
        )

        if not updatedRow:
            return {"success":True,"message": "Not authorized or group does not have enough funds to do this."}

    return {"success":True}

@router.post("/changegroupsettings",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changegroupsettings(request : Request,data : groupJoin,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    GroupId = data.groupid
    SettingType = data.type
    NewOption = data.newoption
    pgPool = await getpgPool()
    Version = CookieData[1]
    Username = CookieData[2]

    if SettingType not in ["manual_approval","group_games_visible","group_funds_visible","allow_enemy_declarations"]:
        return {"success":False,"message": "Invalid group setting type."}

    async with pgPool.acquire() as conn:
        row = await conn.fetchrow(f"""
            UPDATE additional_group_data agd
            SET {SettingType} = $3
            FROM groups g, users u
            WHERE agd.group_id = g.id
            AND g.id = $1
            AND g.groupcreator = u.username
            AND u.username = $2
            AND u.version = $4
            RETURNING agd.group_id
        """,
            GroupId,
            Username,
            NewOption,
            str(Version)
        )

        if not row:
            return {"success": False, "message": "Not authorized to do this action."}

    return {"success":True}