import random
import json
from lib.getPostgresConn import *
from datetime import datetime

async def ForumPost(UserName : str,messageContent : str, thread_id : str, forum_id : str,UserId : int):
    CreatedTimestamp = datetime.utcnow()
    pool = await getpgPool()
    async with pool.acquire() as conn:

        data = await conn.fetchrow("""
            UPDATE users
            SET posts = posts + 1
            WHERE id = $1
            RETURNING createdAt, posts
        """, UserId)

        PostId = random.randint(100000, 999999)
        NewPost = {
            "threadid": int(thread_id),
            "id": PostId,
            "content": messageContent,
            "username": UserName,
            "createdAt": CreatedTimestamp.isoformat(),
            "joinedAt": data["createdat"].isoformat()
        }

        NewPostJSON = json.dumps(NewPost)
        await conn.execute("""
            UPDATE forums
            SET posts_data = posts_data || $2::jsonb,
                posts = posts + 1,
                last_forum_post_username = $3,
                last_forum_post_time = NOW()
            WHERE id = $1;
        """, int(forum_id), NewPostJSON, UserName)
        
async def NewThread(message : str,author : str,forum_id : str,title : str,UserId : int):
    ThreadId = random.randint(100000, 999999)
    PostId = random.randint(100000, 999999)
    CreatedTimestamp = datetime.utcnow()
    NewForumThread = {
        "id": ThreadId,
        "title": title,
        "content": message,
        "author": author,
        "replies": 0,
        "views": 0,
        "post": 0,
        "createdAt": CreatedTimestamp.isoformat()
    }

    NewThreadJSON = json.dumps(NewForumThread)

    pool = await getpgPool()
    async with pool.acquire() as conn:
            data = await conn.fetchrow("""
                UPDATE users
                SET posts = posts + 1
                WHERE id = $1
                RETURNING createdAt, posts
            """, UserId)

            print(data)

            NewForumPost = {
                "id": PostId,
                "threadid": ThreadId, 
                "content": message,
                "author": author,
                "createdAt": CreatedTimestamp.isoformat(),
                "joinedAt": data["createdat"].isoformat(),
                "userid": UserId
            }

            NewPostJSON = json.dumps(NewForumPost)

            row = await conn.fetchrow("""
                UPDATE forums
                SET 
                    threads_data = COALESCE(threads_data, '[]'::jsonb) || $2::jsonb,
                    posts_data = COALESCE(posts_data, '[]'::jsonb) || $3::jsonb,
                    threads = threads + 1,
                    posts = posts + 1,
                    last_forum_post_username = $4,
                    last_forum_post_time = NOW()
                WHERE id = $1
                RETURNING posts, threads;
            """, int(forum_id), NewThreadJSON, NewPostJSON, author)

            print(row["posts"])
            print(row["threads"])