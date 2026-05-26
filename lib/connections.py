from lib.getPostgresConn import *

async def GetConnectionByType(tab : str,offset: int,UserId : int):
    pool = await getpgPool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT
                CASE
                    WHEN $2 = 'Requests' THEN COALESCE(
                        (
                            SELECT jsonb_agg(elem)
                            FROM (
                                SELECT elem
                                FROM jsonb_array_elements(COALESCE(fr.requests, '[]'::jsonb)) AS elem
                                LIMIT $3 OFFSET $4
                            ) sub
                        ),
                        '[]'::jsonb
                    )

                    WHEN $2 = 'Friends' THEN COALESCE(
                        (
                            SELECT jsonb_agg(elem)
                            FROM (
                                SELECT elem
                                FROM jsonb_array_elements(COALESCE(f.friends, '[]'::jsonb)) AS elem
                                LIMIT $3 OFFSET $4
                            ) sub
                        ),
                        '[]'::jsonb
                    )

                    WHEN $2 = 'Followers' THEN COALESCE(
                        (
                            SELECT jsonb_agg(fl.follower_id)
                            FROM (
                                SELECT fl.follower_id
                                FROM follows fl
                                WHERE fl.following_id = u.id
                                LIMIT $3 OFFSET $4
                            ) fl
                        ),
                        '[]'::jsonb
                    )

                    WHEN $2 = 'Followings' THEN COALESCE(
                        (
                            SELECT jsonb_agg(fl.following_id)
                            FROM (
                                SELECT fl.following_id
                                FROM follows fl
                                WHERE fl.follower_id = u.id
                                LIMIT $3 OFFSET $4
                            ) fl
                        ),
                        '[]'::jsonb
                    )

                    ELSE NULL
                END AS data,

                CASE
                    WHEN $2 = 'Requests' THEN COALESCE(jsonb_array_length(fr.requests), 0)
                    WHEN $2 = 'Friends' THEN COALESCE(jsonb_array_length(f.friends), 0)

                    WHEN $2 = 'Followers' THEN u.followers_count
                    WHEN $2 = 'Followings' THEN u.following_count

                    ELSE 0
                END AS amount

            FROM users u
            LEFT JOIN friendrequests fr ON fr.userid = u.id
            LEFT JOIN friends f ON f.userid = u.id
            WHERE u.id = $1
        """, UserId, tab, 10, offset)