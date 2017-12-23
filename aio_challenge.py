import aiohttp
import asyncio
import json
import datetime

# IO
import asyncpg
import aioredis

# https://magic.io/blog/uvloop-blazing-fast-python-networking/
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# CONSTANTS
PG_CONNECTION_STRING = 'postgresql://postgres@localhost/postgres'
PG_POOL = 'pg_pool'
REDIS_CONNECTION_STRING = 'redis://localhost'
REDIS_CONNECTION = 'redis_connection'


# server startup
async def startup(app):
    await connect_pg(app)
    await connect_redis(app)


async def connect_pg(app):
    pg_pool = await asyncpg.create_pool(PG_CONNECTION_STRING, loop=app.loop)
    app[PG_POOL] = pg_pool


async def connect_redis(app):
    redis_connection = await aioredis.create_pool(REDIS_CONNECTION_STRING, loop=app.loop)
    app[REDIS_CONNECTION] = redis_connection


# server cleanup
async def cleanup(app):
    await close_pg(app)
    await close_redis(app)


async def close_pg(app):
    await app['pg_connections'].close()


async def close_redis(app):
    app['redis_connection'].close()
    await app['redis_connection'].wait_closed()


# client code

async def fetch(session, url):
    # with async_timeout.timeout(10):
    async with session.get(url) as response:
        return await response.text()


async def main():
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, 'http://python.org')
        print(html)


# uncomment to run main()
# loop = asyncio.get_event_loop()
# loop.run_until_complete(main())


# server code

from aiohttp import web

routes = web.RouteTableDef()


def python_json_response_view_decorator(handler):
    async def inner(request):
        result = await handler(request)
        return web.json_response(result, dumps=lambda x: json.dumps(x, default=str))

    return inner


def psql_python_view_decorator(handler):
    async def inner(request):
        result = await handler(request)
        return [dict(i) for i in result]

    return inner


async def execute_sql(request, sql_string, *params):
    async with request.app[PG_POOL].acquire() as connection:
        result = await connection.fetch(sql_string, *params)
    return result


# server code
@python_json_response_view_decorator
@psql_python_view_decorator
async def handle(request):
    # name = request.match_info.get('name', "Anonymous")
    # text = "Hello, " + name
    # return web.Response(text=text)
    name = request.query.get('name', '*')
    result = await execute_sql(request, 'SELECT * FROM users WHERE name = $1;', name)
    # return web.json_response(result, dumps=date_enabled_json_dumps)
    return result


@routes.post('/redis/')
@python_json_response_view_decorator
async def set_redis(request):
    post_params = await request.post()
    await request.app[REDIS_CONNECTION].execute('set', post_params.get('key'), post_params.get('value'))
    return {'message': 'successfully inserted key into redis'}


@routes.get('/redis/')
@python_json_response_view_decorator
async def get_redis(request):
    key = request.query.get('key')
    result = await request.app[REDIS_CONNECTION].execute('get', key)
    return result


app = web.Application()
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)
app.router.add_routes(routes)
app.router.add_get('/', handle)
app.router.add_get('/{name}', handle)

web.run_app(app)