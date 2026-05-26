from fastapi import APIRouter,Request,Cookie,Depends
import json
from routes.shared.shared import userlimiter
from lib.getPostgresConn import *
from middleware.authMiddleware import sessionValid

router = APIRouter(
    prefix="/api/forums",
    tags=["forums"]
)

@router.get("",dependencies = [Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def forumsdata(request : Request,Session : str = Cookie(None)):

    pool = await getpgPool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id,title,forums,posts,threads,last_forum_post_username,last_forum_post_time FROM forums
        """)

    for ite in rows:
        print(ite)

    return [
        {
            "threads": item["threads"],
            "posts": item["posts"],
            "id": item["id"],
            "title": item["title"],
            "forums": json.loads(item["forums"]),
            "LastPostTime":  item["last_forum_post_time"].isoformat() if item["last_forum_post_time"] else "",
            "LastPostUser": item["last_forum_post_username"] if item["last_forum_post_username"] else ""
        }
        for item in rows
    ]

@router.get("/{forumId}/threads",dependencies = [Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def forumdata(request : Request,Session : str = Cookie(None),forumId : str = None):

    pool = await getpgPool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT threads_data FROM forums 
            WHERE id = $1
        """,int(forumId))

        if not rows:
            return None

    AllThreads = []
    for item in rows:
        Thread = item["threads_data"]

        if isinstance(Thread,str):
            ThreadData = json.loads(Thread)
        else:
            ThreadData = Thread

        if isinstance(ThreadData,list):
            AllThreads.extend(ThreadData)

    return AllThreads

@router.get("/{forumId}/threads/{threadId}", dependencies=[Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def threaddata(request : Request,Session : str = Cookie(None),threadId : str = None,forumId : str = None):

    try: 
        threadId = int(threadId)
        forumId = int(forumId)
    except (ValueError,TypeError):
        return {"success":False,"message": "ForumId and ThreadId must be numbers."}

    pool = await getpgPool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            WITH base AS (
                SELECT
                    (
                        SELECT t
                        FROM jsonb_array_elements(threads_data) t
                        WHERE (t->>'id')::int = $2
                        LIMIT 1
                    ) AS thread_data,

                    (
                        SELECT jsonb_agg(p)
                        FROM jsonb_array_elements(posts_data) p
                        WHERE (p->>'threadid')::int = $2
                    ) AS posts_data

                FROM forums
                WHERE id = $1
            ),

            enriched AS (
                SELECT
                    jsonb_set(
                        thread_data,
                        '{author}',
                        COALESCE(
                            (
                                SELECT jsonb_build_object(
                                    'username', u.username,
                                    'id', u.id,
                                    'createdAt', u.createdat
                                )
                                FROM users u
                                WHERE u.username = thread_data->>'author'
                            ),
                            '{}'::jsonb
                        )
                    ) AS thread_data,

                    (
                        SELECT jsonb_agg(
                            p || jsonb_build_object(
                                'posts',
                                COALESCE(u.posts, 0)
                            )
                        )
                        FROM jsonb_array_elements(posts_data) AS p
                        LEFT JOIN users u
                            ON u.id = (p->>'userid')::int
                    ) AS posts_data

                FROM base
            )

            SELECT *
            FROM enriched;
            """, int(forumId), int(threadId))
                            
        ThreadData = row["thread_data"] or {}
        PostsData = row["posts_data"] or []

        if isinstance(ThreadData, str):
            ThreadData = json.loads(ThreadData)

        if isinstance(PostsData, str):
            PostsData = json.loads(PostsData)

        print(ThreadData)
        print(PostsData)

    return {
        "id": ThreadData["id"],
        "title": ThreadData["title"],
        "content": ThreadData.get("content", ""),
        "views": ThreadData.get("views", 0),
        "replies": ThreadData.get("replies", 0),
        "createdAt": ThreadData["createdAt"],
        "posts": PostsData,
        "author": ThreadData.get("author", {})
    }