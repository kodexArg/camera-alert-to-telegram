#
credits: https://stackoverflow.com/questions/13688328/list-rtsp-streams-of-network-camera/61666478#61666478
#

import ipaddress
import cv2

# need to know those before hand. I got IP with Nmap
usr = 'admin'
pwd = 'admin'
ip = '192.168.1.1'
start_ip = '192.168.1.1'
end_ip = '192.168.1.254'

# I took the url patterns and also included some variations, just to be sure...
urls = [f'rtsp://{usr}:{pwd}@{ip}:554/cam/realmonitor?channel=1&subtype=0',
        f'rtsp://{ip}:554/live=2.2&username={usr}&password={pwd}',
        f'rtsp://{usr}:{pwd}@{ip}:554/1',
        f'rtsp://{usr}:{pwd}@{ip}:554/stream1',
        f'rtsp://{usr}:{pwd}@{ip}:554/Stream1',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp?',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp',
        f'rtsp://{ip}:554/videostream.asf?user={usr}&pwd={pwd}',
        f'rtsp://{ip}:554/ucast/11',
        f'rtsp://{ip}:554/11',
        f'rtsp://{ip}:554/12',
        f'rtsp://{ip}:554/live0.264',
        f'rtsp://{ip}:554/mpeg4cif',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp?',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp',
        f'rtsp://{ip}:554/live1.264',
        f'rtsp://{ip}:554/cam1/h264',
        f'rtsp://{ip}:554/mpeg4cif',
        f'rtsp://{ip}:554/ucast/11',
        f'rtsp://{ip}:554/ROH/channel/11',
        f'rtsp://{ip}:554/user={usr}_password={pwd}_channel=1_stream=0.sdp',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp?',
        f'rtsp://{ip}:554/user={usr}_password={pwd}_channel=1_stream=0.sdp',
        f'rtsp://{ip}:554/user={usr}_password={pwd}_channel=1_stream=0.sdp?',
        f'rtsp://{ip}:554/cam1/mpeg4?user={usr}&pwd={pwd}',
        f'rtsp://{ip}:554/h264_stream',
        f'rtsp://{ip}:554/live/ch0',
        f'rtsp://{ip}:554/live/ch1',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp?',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=1.sdp?',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=0&stream=1.sdp?',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=0&stream=0.sdp?',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=0.sdp',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=1&stream=1.sdp',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=0&stream=1.sdp',
        f'rtsp://{ip}:554/user={usr}&password={pwd}&channel=0&stream=0.sdp',
        f'rtsp://{usr}:{pwd}@{ip}:554/ucast/11',
        f'rtsp://{usr}:{pwd}@{ip}:554/11',
        f'rtsp://{usr}:{pwd}@{ip}:554/12',
        f'rtsp://{usr}:{pwd}@{ip}:554/live0.264',
        f'rtsp://{usr}:{pwd}@{ip}:554/mpeg4cif',
        f'rtsp://{usr}:{pwd}@{ip}:554/live1.264',
        f'rtsp://{usr}:{pwd}@{ip}:554/cam1/h264',
        f'rtsp://{usr}:{pwd}@{ip}:554/mpeg4cif',
        f'rtsp://{usr}:{pwd}@{ip}:554/ucast/11',
        f'rtsp://{usr}:{pwd}@{ip}:554/ROH/channel/11',
        f'rtsp://{usr}:{pwd}@{ip}:554/h264_stream',
        f'rtsp://{usr}:{pwd}@{ip}:554/live/ch0',
        f'rtsp://{usr}:{pwd}@{ip}:554/live/ch1',
       ]


def test_url(url):
    # try to open the stream
    cap = cv2.VideoCapture(url)
    ret = cap.isOpened()  # if it was succesfully opened, that's the URL you need
    cap.release()
    return ret


def cycle_ips(start_ip, end_ip):
    start = ipaddress.IPv4Address(start_ip)
    end = ipaddress.IPv4Address(end_ip)

    for ip_int in range(int(start), int(end) + 1):
        ip = ipaddress.IPv4Address(ip_int)
        for url in urls:
            if test_url(url):
                print(url)

def main():
    cycle_ips(start_ip, end_ip)



if __name__ == '__main__':
    main()
# for url in urls:
#     if test_url(url):
#         print(url)
    
