import requests
import re
from threading import Thread
import time
import json
from email.mime.text import MIMEText
from email.header import Header
from email.mime.multipart import MIMEMultipart
import smtplib
import asyncio
from datetime import datetime, timedelta
from email.utils import formataddr
from concurrent.futures import ProcessPoolExecutor, as_completed


def remove_after_wm(s):
    # 查找'W'或'M'首次出现的位置
    # 使用min函数和find方法确保我们找到的是两者中较早出现的一个
    # 如果'W'或'M'都不存在，find会返回-1，而min(-1, -1)也是-1
    pos_w = s.find('W')
    pos_m = s.find('M')
    pos_f = s.find('F')

    if pos_w != -1 and pos_m != -1 and pos_f != -1:
        pos = min(pos_w, pos_m, pos_f)
    elif pos_w != -1:
        pos = pos_w
    elif pos_m != -1:
        pos = pos_m
    elif pos_f != -1:
        pos = pos_f
    else:
        pos = -1  # 表示'W'和'M'都不存在

    return s[:pos]


def contains_number_or_you(s):
    # 检查是否包含数字
    if any(char.isdigit() for char in s):
        return True
    # 检查是否包含“有”
    if "有" in s:
        return True
    # 如果都不包含，则返回False
    return False


async def send_mail(mail_body, receivers):
    # 发件人邮箱账号
    sender = ''
    # 发件人邮箱授权码（不是QQ密码）
    password = ''  # 授权码

    # SMTP服务器地址
    smtp_server = 'smtp.qq.com'
    # SMTP服务器端口，对于QQ邮箱，使用SSL的465端口
    smtp_port = 465

    # 邮件内容
    subject = '抢到火车票了！'
    # HTML邮件正文
    html_body = mail_body

    # 邮件接收者
    # receiver = ''

    # 创建邮件对象，指定内容为HTML
    message = MIMEText(html_body, 'html', 'utf-8')
    # 设置From头部，使用formataddr函数来正确设置完整的From头部信息
    message['From'] = formataddr(('发件人姓名', sender))
    # 设置To头部，同样使用Header
    # message['To'] = Header(receiver, 'utf-8')
    # 设置Subject头部，对于中文主题也使用Header
    message['Subject'] = Header(subject, 'utf-8')

    try:
        # 创建SMTP SSL连接
        smtpObj = smtplib.SMTP_SSL(smtp_server, smtp_port)
        smtpObj.login(sender, password)  # 登录到SMTP服务器

        # 如果receivers是单个字符串，则转换为列表
        if isinstance(receivers, str):
            receivers = [receivers]

        # 发送邮件给多个接收者
        smtpObj.sendmail(sender, receivers, message.as_string())
        print("邮件发送成功")
        smtpObj.quit()
    except smtplib.SMTPException as e:
        print("邮件发送失败:", e)


def list_to_html(data):
    print("+++++++++++++++++++")
    # print(data)
    # print(type(data))
    print("++++++++++++++++++")
    headers = [
        "列车号", "起点站", "途经站1", "途经站2", "终点站",
        "出发时间", "到达时间", "耗费时间", "暂无", "暂无",
        "暂无", "暂无", "暂无", "座位数目", "优选一等座",
        "座位数目", "座位数目", "软卧/动卧", "座位数目", "座位数目", "无座", "座位数目", "硬卧,二等卧", "硬座", "二等座", "一等座", "商务座,特等座", "座位数目"
    ]

    # 构造HTML表格的开头部分，包括CSS样式
    html_table = '''  
    <style>  
    .table-container {  
        height: 90vh;  /* 根据视口高度设置，以适应不同屏幕 */  
        overflow-y: auto; /* 允许垂直滚动 */  
        display: block; /* 可能需要，取决于布局 */  
        width: 100%; /* 或固定宽度 */  
    }  
    th {  
        position: sticky;  
        top: 0;  
        background-color: #f9f9f9; /* 表头背景色 */  
    }  
    table {  
        width: 100%; /* 确保表格宽度与容器相同 */  
        border-collapse: collapse; /* 边框合并 */  
    }  
    th, td {  
        border: 1px solid #ddd; /* 边框样式 */  
        padding: 8px; /* 单元格内边距 */  
        text-align: left; /* 文本对齐方式 */  
    }  
    </style>  
    <div class="table-container">  
    <table>  
    <thead>  
    <tr>  
    '''
    for header in headers:
        html_table += f'<th>{header}</th>'
    html_table += '''  
    </tr>  
    </thead>  
    <tbody>  
    '''

    # 遍历数据，并为每一项添加一行到表格体（tbody）中
    for item in data:
        columns = item.split('|')
        # 填充缺失的列
        columns += [''] * (len(headers) - len(columns))
        html_row = '<tr>' + ''.join(f'<td>{column}</td>' for column in columns) + '</tr>\n'
        html_table += html_row

        # 添加表格的结尾部分
    html_table += '''  
    </tbody>  
    </table>  
    </div>  
    '''

    # 返回完整的HTML字符串
    print(html_table)
    return html_table


def check_http_code(http_code):
    """
    检查接口返回httpcode 是否200
    :param http_code:
    :return: True or False
    """
    if http_code == 200:
        return True
    else:
        return False


def compare_time(now, delay_time):
    """
    比较时间大小
    :param now: 现在时间
    :param delay_time: 延期发送邮件时间
    :return: Boolean
    """
    if now >= delay_time:
        return True
    else:
        return False


def delay_time(email_delay_time):
    """
    延迟时间
    :param now: 现在的时间
    :param delay_time_info: 要延迟的时间
    :return: email_alert_delay_time 延迟后的时间
    """
    if email_delay_time:
        # 获取当前时间
        now_time = datetime.now()
        # 创建延迟时间
        if email_delay_time[0] == 1:
            alert_time_delay = timedelta(hours=email_delay_time[1])  # hours 小时 minutes 分钟
        else:
            alert_time_delay = timedelta(minutes=email_delay_time[1])  # hours 小时 minutes 分钟
        # 将当前时间加上延迟的时间
        email_alert_delay_time = now_time + alert_time_delay
    else:
        email_alert_delay_time = None

    return email_alert_delay_time


def train_info(url, address, receivers, sleep_time=10, user_focus_train=None, email_delay_time=None):
    """
    =========== dreamshao 12306查询余票函数调用指南=========

    支持多线程查询火车票余票，使用教程：
    登录12306 网站 https://www.12306.cn/index/
    选择起点，终点，时间 点击查询
    此时页面跳转到列车详情页面，打开network 面板，再次点击查询抓取查询接口
    注意： 此时可能会用2个接口请求，一个是火车列表信息， 一个是中转信息
    我们需要的url 是这样的： https://kyfw.12306.cn/otn/leftTicket/queryG?leftTicketDTO.train_date=2024-09-30&leftTicketDTO.from_station=SJP&leftTicketDTO.to_station=XTP&purpose_codes=ADULT
    然后将其作为Url 参数传入，然后选择改url对应的COOKIE, 在程序中替换之前的即可！

    =========== dreamshao 12306查询余票函数调用指南=========
    :param url: 请求url
    :param address: 火车起点重点： 北京-----> 邯郸
    :param user_focus_train: 你关注的列车有票才会发送邮件，格式是list ['G3433','K333']
    :param sleep_time: 请求接口休眠时间
    :param email_delay_time 邮件延迟发送时间，就是当前不希望每次都收到通知，只是希望间隔多久通知一次， 目前是 minutes, hours 格式是(1, 0.5) 是 小时, 其余是按照分钟处理
    :param receivers 邮件接收人 可以传递一个列表例如 ['123232@qq.com','3333@qq.com]  多人接收邮件
    :return:
    """
    if url == "" or address == "" or receivers == "":
        return "please input right url or address or receivers"
    print(
        f"当前请求地址是{url},请求火车票方向是{address},邮件接收人是{receivers},请求间隔时间是{sleep_time}秒,用户关注的火车列表是{user_focus_train},邮件间隔报警时间是{email_delay_time}")
    time_info = url.split('train_date=')[1].split("&")[0]  # 出发时间
    global send_info_type, send_numbers, send_email_all_type, send_all_numbers, email_alert_delay_type, email_alert_delay_time  # 关注的火车发送邮件状态
    send_info_type = False  # 关注火车列表发送状态
    send_email_all_type = False  # 所有火车列表发送状态
    send_numbers = 0
    send_all_numbers = 0
    numbers = 0
    email_alert = []
    email_alert_delay_time = delay_time(email_delay_time)

    while True:
        # 获取当前时间
        now = datetime.now()
        # 是否有票的标志
        has_ticket = False
        print(f"当前正在抢{address}的火车票")
        payload = {}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Cookie': 'JSESSIONID=6571054C8C61F63A5F32C82A1A340BED; guidesStatus=off; _big_fontsize=0; highContrastMode=defaltMode; cursorStatus=off; BIGipServerpool_index=821035530.43286.0000; route=6f50b51faa11b987e576cdb301e545c4; BIGipServerotn=670040586.24610.0000'

        }

        time.sleep(sleep_time)
        response = requests.request("GET", url, headers=headers, data=payload)
        if check_http_code(response.status_code):
            re_json = json.loads(response.text)
            len_nums = len(re_json['data']['result'])
            # print(re_json['data']['result'])
            for i in (re_json['data']['result']):
                numbers += 1
                try:
                    if "|N|" in i:
                        # print(i.split("预订")[1][14:].split("|N|")[0])
                        train_info = i.split("预订")[1][14:].split("|N|")[0]
                        print(train_info)
                    else:
                        # print(i.split("预订")[1][14:].split("|Y|")[0])
                        train_info = i.split("预订")[1][14:].split("|Y|")[0]
                        print(train_info)
                    info = remove_after_wm(str((i.split("预订")[1][14:]).split("2024")[1]))
                    # print(info)
                    # print(info[20:][:17])
                    print(numbers)
                    print(len_nums)
                    if contains_number_or_you(info[20:][:17]):
                        print(info)
                        print("有票啦！")
                        email_info = train_info + " " + info
                        if email_info not in email_alert:
                            email_alert.append(email_info)
                    if numbers == len_nums:
                        # 替换成表格
                        email_alert_update = list_to_html(email_alert)
                        # print(email_alert_update)
                        # print(type(email_alert_update))
                        if user_focus_train:
                            print("===================")
                            print(f"用户开启了筛选火车发送邮件，当前选择的是{user_focus_train}")
                            print("===================")
                            for user_train in user_focus_train:
                                for train_single_info in email_alert:
                                    if user_train in train_single_info:
                                        send_info_type = True
                            if send_info_type and send_numbers == 0:
                                print("===================")
                                print(f"现在正在查看{address},现在时间{now}")
                                print(f"用户开启了筛选火车发送邮件，存在相同列车信息，将会发送邮件！")
                                print("===================")
                                send_numbers = 1
                                asyncio.run(send_mail(mail_body=f"抢到了{time_info},{address}的票{email_alert_update}",
                                                      receivers=receivers))
                                email_alert.clear()

                            elif send_numbers != 0 and send_info_type and email_alert_delay_time:
                                print("===================")
                                print("当前设置了邮件发送延迟")
                                print(f"现在正在查看{address},现在时间{now},定时清空列表时间{email_alert_delay_time}")
                                print(
                                    f"当前用户开启了筛选火车发送邮件，存在相同列车信息, 但是在当前设置的延迟发送邮件中, 下次发送时间是{email_alert_delay_time}之后, 所以此次不会发送邮件！")
                                print("===================")
                                email_alert.clear()
                                if compare_time(now, email_alert_delay_time):
                                    email_alert.clear()
                                    send_numbers = 0  # 专注火车列表发送次数归零
                                    # send_all_numbers = 0  # 已经发送所有火车有票的记录
                                    # send_email_all_type = True
                                    print("清空列表,重新开始发送邮件")
                                    asyncio.run(send_mail(mail_body=f"抢到了{time_info},{address}的票{email_alert_update}",
                                                          receivers=receivers))
                                    email_alert_delay_time = delay_time(email_delay_time)
                                    print(f"现在正在查看{address},现在时间{now},定时清空列表时间{email_alert_delay_time}")
                            else:
                                print("===================")
                                print(f"现在正在查看{address},现在时间{now}")
                                print(f"用户开启了筛选火车发送邮件，不存在相同列车信息，不会发送邮件！")
                                email_alert.clear()
                                print("===================")
                        elif not send_email_all_type and send_all_numbers == 0 and email_alert_delay_time:
                            """
                            首次发送全部有票的火车, 且当前存在邮件延迟发送时间设置
                            """
                            print("===================")
                            print("首次发送全部有票的火车,当前设置了邮件发送延迟")
                            print(f"现在正在查看{address},现在时间{now},定时清空列表时间{email_alert_delay_time}")
                            print("====================")
                            send_all_numbers += 1
                            send_email_all_type = True
                            asyncio.run(send_mail(mail_body=f"抢到了{time_info},{address}的票{email_alert_update}",
                                                  receivers=receivers))
                            email_alert.clear()

                        elif send_email_all_type and send_all_numbers == 1 and email_alert_delay_time:
                            """
                             当前存在邮件延迟发送时间设置
                            """
                            print("===================")
                            print("当前设置了邮件发送延迟")
                            print(f"现在正在查看{address},现在时间{now},定时清空列表时间{email_alert_delay_time}")
                            print("====================")
                            email_alert.clear()
                            if compare_time(now, email_alert_delay_time):
                                email_alert.clear()
                                # # send_numbers = 0  # 专注火车列表发送次数归零
                                # send_all_numbers = 1  # 已经发送所有火车有票的记录
                                # send_email_all_type = T  # 回到首次发送的状态
                                print("清空列表,重新开始发送邮件")
                                asyncio.run(send_mail(mail_body=f"抢到了{time_info},{address}的票{email_alert_update}",
                                                      receivers=receivers))
                                email_alert_delay_time = delay_time(email_delay_time)
                                print(f"现在正在查看{address},现在时间{now},定时清空列表时间{email_alert_delay_time}")

                        else:
                            print("===================")
                            print(f"现在正在查看{address},现在时间{now}")
                            print("当前未设置延迟发送邮件,将即可发送邮件")
                            print("===================")
                            asyncio.run(send_mail(mail_body=f"抢到了{time_info},{address}的票{email_alert_update}",
                                                  receivers=receivers))
                            email_alert.clear()

                        numbers = 0  # 控制整体的数目归零
                except Exception as e:
                    print(e)
                    print(remove_after_wm(str((i.split("起售")[1][14:]).split("2024")[1])))
                print(">>>>>")
        else:
            return f"12306接口请求失败, 状态码是{response.status_code}"


if __name__ == "__main__":
    """
    train_info 函数传递顺序(url, address, receivers, sleep_time, user_focus_train, email_delay_time)
    """
    query_list = [
        (
            "https://kyfw.12306.cn/otn/leftTicket/queryG?leftTicketDTO.train_date=2024-10-09&leftTicketDTO.from_station=SJP&leftTicketDTO.to_station=HDP&purpose_codes=ADULT",
            "石家庄---->邯郸", ["1548645@qq.com", "3221294@qq.com"], 10, ['K3423', 'G345'], (2, 1)),  # 到邯郸
        (
            "https://kyfw.12306.cn/otn/leftTicket/queryG?leftTicketDTO.train_date=2024-10-09&leftTicketDTO.from_station=SJP&leftTicketDTO.to_station=XTP&purpose_codes=ADULT",
            "石家庄---->邢台", ["1548645@qq.com", "321294@qq.com"], 20, [], (2, 2))  # 到邢台
    ]

    with ProcessPoolExecutor(max_workers=2) as executor:
        # 提交任务，每个任务都接收一个args元组，自动解包为多个参数
        futures = [executor.submit(train_info, *args) for args in query_list]
        # 等待所有任务完成
        try:
            for future in as_completed(futures):
                # 处理可能的异常
                result = future.result()
                print(f"Received result: {result}")
        except Exception as e:
            print(f"进程出错了{e}")
