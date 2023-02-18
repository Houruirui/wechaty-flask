from aioflask import Flask
from aioflask import request
from Config import WECHAT_SEVER_CONFIG
import concurrent.futures
from threading import Thread
import threading
import itertools

from wechaty import Wechaty, Message, WechatyPlugin, Room, WechatyOptions
from wechaty_puppet import *
import os
import asyncio
import json
import traceback

app = Flask(__name__)

WECHATY_PUPPET_SERVICE_TOKEN = ''
WECHATY_PUPPET = 'wechaty-puppet-service'

os.environ['WECHATY_PUPPET_SERVICE_TOKEN'] = WECHATY_PUPPET_SERVICE_TOKEN
os.environ['WECHATY_PUPPET'] = WECHATY_PUPPET
os.environ['WECHATY_PUPPET_SERVICE_ENDPOINT'] = "0.0.0.0:9001"


class WechatBot():

    def __init__(self):
        print("need to Init wechat bot!")
        self.bot: Wechaty = None
        asyncio.get_event_loop().run_until_complete(self.init_wechat_bot())

    async def init_wechat_bot(self):
        puppet_options = PuppetOptions()
        puppet_options.token = WECHATY_PUPPET_SERVICE_TOKEN

        options = WechatyOptions()
        # options.name = self.my_wechat_id
        options.puppet = WECHATY_PUPPET
        options.puppet_options = puppet_options

        self.bot = Wechaty(options)
        await self.bot.init_puppet()
        await self.bot.init_puppet_event_bridge(self.bot.puppet)
        self.bot.puppet._init_puppet()
        # await self.bot.puppet.logout()
        # print(self.bot.puppet.login_user_id)
        async for response in self.bot.puppet.puppet_stub.event():
            if response is not None:
                payload_data: dict = json.loads(response.payload)
                if response.type == int(EventType.EVENT_TYPE_SCAN):
                    print('receive scan info,', payload_data)
                    # create qr_code
                    payload = EventScanPayload(
                        status=ScanStatus(payload_data['status']),
                        qrcode=payload_data.get('qrcode', None),
                        data=payload_data.get('data', None)
                    )
                    print('scan payload_data', payload_data)
                    self.bot.puppet._event_stream.emit('scan', payload)

                elif response.type == int(EventType.EVENT_TYPE_LOGIN):
                    print('receive login info ', payload_data)
                    # print('login payload_data', payload_data)
                    event_login_payload = EventLoginPayload(
                        contact_id=payload_data['contactId'])
                    self.bot.puppet.login_user_id = payload_data.get('contactId', None)
                    self.bot.puppet._event_stream.emit('login', event_login_payload)
                    break

                elif response.type == int(EventType.EVENT_TYPE_READY):
                    print('receive ready info ', payload_data)
                    payload = EventReadyPayload(**payload_data)
                    self.bot.puppet._event_stream.emit('ready', payload)
                    break

                elif response.type == int(EventType.EVENT_TYPE_ROOM_TOPIC):
                    print('receive room-topic info <%s>', payload_data)
                    payload = EventRoomTopicPayload(
                        changer_id=payload_data.get('changerId'),
                        new_topic=payload_data.get('newTopic'),
                        old_topic=payload_data.get('oldTopic'),
                        room_id=payload_data.get('roomId'),
                        timestamp=payload_data.get('timestamp')
                    )
                    self.bot.puppet._event_stream.emit('room-topic', payload)
                elif response.type == int(EventType.EVENT_TYPE_DONG):
                    print('receive dong info <%s>', payload_data)
                    payload = EventDongPayload(**payload_data)
                    self.bot.puppet._event_stream.emit('dong', payload)

                elif response.type == int(EventType.EVENT_TYPE_MESSAGE):
                    # payload = get_message_payload_from_response(response)
                    print('receive message info <%s>', payload_data)
                    event_message_payload = EventMessagePayload(
                        message_id=payload_data['messageId'])
                    self.bot.puppet._event_stream.emit('message', event_message_payload)
                elif response.type == int(EventType.EVENT_TYPE_HEARTBEAT):
                    print('receive heartbeat info <%s>', payload_data)
                    # Huan(202005) FIXME:
                    #   https://github.com/wechaty/python-wechaty-puppet/issues/6
                    #   Workaround for unexpected server json payload key: timeout
                    # if 'timeout' in payload_data:
                    #     del payload_data['timeout']
                    payload_data = {'data': payload_data['data']}
                    payload = EventHeartbeatPayload(**payload_data)
                    self.bot.puppet._event_stream.emit('heartbeat', payload)

                elif response.type == int(EventType.EVENT_TYPE_ERROR):
                    print('receive error info <%s>', payload_data)
                    payload = EventErrorPayload(**payload_data)
                    self.bot.puppet._event_stream.emit('error', payload)
                elif response.type == int(EventType.EVENT_TYPE_FRIENDSHIP):
                    print('receive friendship info <%s>', payload_data)
                    payload = EventFriendshipPayload(
                        friendship_id=payload_data.get('friendshipId')
                    )
                    self.self.bot.puppet._event_stream.emit('friendship', payload)

                elif response.type == int(EventType.EVENT_TYPE_ROOM_JOIN):
                    print('receive room-join info <%s>', payload_data)
                    payload = EventRoomJoinPayload(
                        invited_ids=payload_data.get('inviteeIdList', []),
                        inviter_id=payload_data.get('inviterId'),
                        room_id=payload_data.get('roomId'),
                        timestamp=payload_data.get('timestamp')
                    )
                    self.self.bot.puppet._event_stream.emit('room-join', payload)
                elif response.type == int(EventType.EVENT_TYPE_ROOM_INVITE):
                    print('receive room-invite info <%s>', payload_data)
                    payload = EventRoomInvitePayload(
                        room_invitation_id=payload_data.get(
                            'roomInvitationId', None)
                    )
                    self.bot.puppet._event_stream.emit('room-invite', payload)

                elif response.type == int(EventType.EVENT_TYPE_ROOM_LEAVE):
                    print('receive room-leave info <%s>', payload_data)
                    payload = EventRoomLeavePayload(
                        removed_ids=payload_data.get('removeeIdList', []),
                        remover_id=payload_data.get('removerId'),
                        room_id=payload_data.get('roomId'),
                        timestamp=payload_data.get('timestamp')
                    )
                    self.bot.puppet._event_stream.emit('room-leave', payload)

                elif response.type == int(EventType.EVENT_TYPE_LOGOUT):
                    print('receive logout info <%s>', payload_data)
                    payload = EventLogoutPayload(
                        contact_id=payload_data['contactId'],
                        data=payload_data.get('data', None)
                    )
                    self.login_user_id = None
                    self.bot.puppet._event_stream.emit('logout', payload)

                elif response.type == int(EventType.EVENT_TYPE_UNSPECIFIED):
                    pass
        for room_name, values in ROOMS.items():
            room = self.bot.Room.load(values[0])
            await room.ready()
            ROOMS[room_name][1] = room
            print(room_name, "ready!", room)
        print(ROOMS)


class EventLoopThread(threading.Thread):
    loop = None
    _count = itertools.count(0)

    def __init__(self):
        self.started = threading.Event()
        name = f"{type(self).__name__}-{next(self._count)}"
        super().__init__(name=name, daemon=True)

    def __repr__(self):
        loop, r, c, d = self.loop, False, True, False
        if loop is not None:
            r, c, d = loop.is_running(), loop.is_closed(), loop.get_debug()
        return (
            f"<{type(self).__name__} {self.name} id={self.ident} "
            f"running={r} closed={c} debug={d}>"
        )

    def run(self):
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.call_later(0, self.started.set)

        try:
            loop.run_forever()
        finally:
            try:
                shutdown_asyncgens = loop.shutdown_asyncgens()
            except AttributeError:
                pass
            else:
                loop.run_until_complete(shutdown_asyncgens)
            try:
                shutdown_executor = loop.shutdown_default_executor()
            except AttributeError:
                pass
            else:
                loop.run_until_complete(shutdown_executor)
            asyncio.set_event_loop(None)
            loop.close()

    def stop(self):
        loop, self.loop = self.loop, None
        if loop is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        self.join()


_lock = threading.Lock()
_loop_thread = None


def get_event_loop():
    global _loop_thread

    if _loop_thread is None:
        with _lock:
            if _loop_thread is None:
                _loop_thread = EventLoopThread()
                _loop_thread.start()
                # give the thread up to a second to produce a loop
                _loop_thread.started.wait(1)

    return _loop_thread.loop


def stop_event_loop():
    global _loop_thread
    with _lock:
        if _loop_thread is not None:
            _loop_thread.stop()
            _loop_thread = None


def run_coroutine(coro):
    """Run the coroutine in the event loop running in a separate thread

    Returns a Future, call Future.result() to get the output

    """
    return asyncio.run_coroutine_threadsafe(coro, get_event_loop())





async def send_wechat_message(room_str, message):
    global ROOMS
    room = ROOMS[room_str][1]
    if room:
        await room.say(message)
        return True
    return False


@app.route('/sendmessage', methods=['POST'])
def send_message():
    try:
        res = request.json
        if res:
            room_str = res['room']
            message = res['message']
            asyncio.create_task(send_wechat_message(room_str, message))
            return "success"
    except Exception:
        print("send msg fail, error:", traceback.format_exc())
    return 'fail'

ROOMS = {
    "快了一家人": ["1111111111111@chatroom", None],
    "跟单一万起家": ["222222222@chatroom", None]
}

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    bot = WechatBot()
    app.run(debug=False, host='0.0.0.0', port="9999")
