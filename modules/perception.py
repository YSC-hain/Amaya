import datetime

class Perception_Layer():
    def format_message(message):
        now_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        result = ''
        # ToDo: 实现图片与视频的识别
        for item in message:
            if item['type'] == 'text':
                result += '[' + now_time_str + '] ' + item['data']['text'].strip()
        
        return result