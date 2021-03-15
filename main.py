import aiohttp
from aiohttp import web, BasicAuth, hdrs
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from aiohttp_basicauth import BasicAuthMiddleware

Base = declarative_base()


class Advertisement(Base):
    __tablename__ = 'advertisement'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(String(300), nullable=False)
    date = Column(DateTime, default=datetime)
    creator = Column(String(300), nullable=False)

    def __repr__(self):
        return f'Объявление {self.title}, {self.description}, {self.creator}, {self.date}'


engine = create_engine('sqlite:///adv.db')
DBSession = sessionmaker(bind=engine)
Base.metadata.create_all(engine)
routes = web.RouteTableDef()

users = {
    "john": generate_password_hash("hello"),
    "susan": generate_password_hash("bye")
}


class CustomBasicAuth(BasicAuthMiddleware):
    async def verify_password(username, password, request):
        if username in users and \
                check_password_hash(users.get(username), password):
            return username


auth = CustomBasicAuth()
app = web.Application(middlewares=[auth])
app.add_routes(routes)


@routes.post('/create-adv/')
@auth.required
async def create_adv(request: web.Request):
    auth_adv = BasicAuth.decode(auth_header=request.headers[hdrs.AUTHORIZATION])
    db_session = DBSession()
    new_adv = await request.json()
    title = new_adv["title"]
    description = new_adv["description"]
    date = datetime.datetime.now()
    creator = auth_adv.login
    new_adv = Advertisement(title=title, description=description, date=date, creator=creator)
    try:
        async with aiohttp.ClientSession():
            db_session.add(new_adv)
            db_session.commit()
    except IntegrityError:
        return web.json_response({"error": 'При добавлении объявления произошла ошибка'})
    return web.Response(text='Объявление успешно добавлено')


@routes.get('/advertisements')
async def advertisements(request):
    db_session = DBSession()
    async with aiohttp.ClientSession():
        advertisements = db_session.query(Advertisement).all()
        if not advertisements:
            raise web.HTTPNotFound(text='Объявлений нет')
        advertisements_all = ''
        for adv in advertisements:
            adv_str = f'Объявление №{adv.id} "{adv.title}": {adv.description} \n'
            advertisements_all = advertisements_all + adv_str
        return web.Response(text=advertisements_all)


@routes.get('/advertisements/{adv_id}')
async def advertisement_page(request):
    db_session = DBSession()
    async with aiohttp.ClientSession():
        adv_id = request.match_info['adv_id']
        if adv_id.isdigit():
            adv_id = int(adv_id)
        else:
            raise web.HTTPBadRequest(text='Неверный запрос')
        adv_page = db_session.query(Advertisement).filter(Advertisement.id == adv_id).all()
        if not adv_page:
            raise web.HTTPNotFound(text=f"Объявление №{adv_id} отсутствует в базе")
        return web.Response(text=str(adv_page))


@routes.delete('/advertisements/{adv_id}/delete')
@auth.required
async def advertisement_delete(request: web.Request):
    auth_adv = BasicAuth.decode(auth_header=request.headers[hdrs.AUTHORIZATION])
    db_session = DBSession()
    async with aiohttp.ClientSession():
        adv_id = request.match_info['adv_id']
        if adv_id.isdigit():
            adv_id = int(adv_id)
        else:
            raise web.HTTPBadRequest(text='Неверный запрос')
        adv_page = db_session.query(Advertisement).filter(Advertisement.id == adv_id).first()
        if adv_page:
            if adv_page.creator == auth_adv.login:
                db_session.delete(adv_page)
                db_session.commit()
                return web.Response(text=f'Объявление №{adv_id} удалено')
            else:
                raise web.HTTPNotFound(text=f"Удалять объявление может только его автор")
        else:
            raise web.HTTPNotFound(text=f"Объявление №{adv_id} отсутствует в базе")


@routes.patch('/advertisements/{adv_id}/update')
@auth.required
async def update_advertisement(request: web.Request):
    auth_adv = BasicAuth.decode(auth_header=request.headers[hdrs.AUTHORIZATION])
    db_session = DBSession()
    updates = await request.json()
    adv_id = request.match_info['adv_id']
    adv_updates = db_session.query(Advertisement).filter(Advertisement.id == adv_id).first()
    if updates.get('title'):
        adv_updates.title = updates['title']
    if updates.get('description'):
        adv_updates.description = updates['description']
    adv_updates.date = datetime.datetime.now()
    async with aiohttp.ClientSession():
        if adv_updates.creator == auth_adv.login:
            db_session.commit()
            return web.Response(text=f'Объявление №{adv_id} отредактировано')
        else:
            raise web.HTTPNotFound(text=f"Редактировать объявление может только его автор")


if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8000)
