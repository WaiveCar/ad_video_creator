from base64 import b64decode
from urllib.parse import urlsplit
import logging, os, sys, time, subprocess, argparse
import requests
import trio
from trio_cdp import open_cdp, emulation, page, target

log_level = 'INFO'
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger('create_ad_video')
logging.getLogger('trio-websocket').setLevel(logging.WARNING)

frames = []

def parse_args():
  parser = argparse.ArgumentParser(description="Generate a video of the given URL")
  parser.add_argument("-W", "--width", type=int, 
                      help="browser/video width",
                      default=1920)
  parser.add_argument("-H", "--height", type=int, 
                      help="browser/video height",
                      default=1080)
  parser.add_argument("-F", "--fps", type=float, 
                      help="video FPS",
                      default=60.0)
  parser.add_argument("-f", "--first", type=float, 
                      help="first frame time (secs)",
                      default=0.3)
  parser.add_argument("-l", "--last", type=float, 
                      help="last frame time (secs)",
                      default=None)
  parser.add_argument("-O", "--output",
                      help="name of video file (.mp4 suffix will be added)",
                      default=None)
  parser.add_argument("-D", "--dir",
                      help="directory to save video file into",
                      default="output")
  parser.add_argument("-C", "--cdb_host_port",
                      help="Chrome DevTools host:port",
                      default="127.0.0.1:9222")
  parser.add_argument("url", help="URL to convert to a video")
  return parser.parse_args()

def get_ws_debugger_url(host_and_port):
  r = requests.get('http://{}/json/version'.format(host_and_port))
  j = r.json()
  return j.get('webSocketDebuggerUrl')

async def capture_screencast(session):
  global frames, page_load_time

  async def wait_for_page_load(cancel_scope):
    frame_count = len(frames)
    while True:
      await trio.sleep(2)
      if frame_count == len(frames):
        logger.info("No frames for 2 seconds.")
        await page.stop_screencast()
        cancel_scope.cancel()
      else:
        frame_count = len(frames)
  
  async def frame_saver():
    async for sc_data in session.listen(page.ScreencastFrame):
      frames.append(sc_data)
      logger.info('Saved frame to memory')
      await page.screencast_frame_ack(sc_data.session_id)
    
  logger.info('Starting Screencast')
  await page.start_screencast(format_='png', every_nth_frame=1)
  async with trio.open_nursery() as nursery:
    nursery.start_soon(wait_for_page_load, nursery.cancel_scope)
    
    logger.info('Navigating to %s', args.url)
    async with session.wait_for(page.LoadEventFired):
      nursery.start_soon(frame_saver)
      await page.navigate(url=args.url)
      page_load_time = time.time()


def write_frames(frames):
  i = 1
  last_frame_time = None
  with open('/tmp/frames.txt', 'w') as frames_list:
    for f in sorted(frames, key=lambda x: x.metadata.timestamp):
      if f.metadata.timestamp < page_load_time:
        i += 1
        continue
      image_name = '/tmp/frame-{:03}.png'.format(i)
      if args.last is not None and i == len(frames):
        frame_duration = args.last
      else:
        frame_duration = f.metadata.timestamp - last_frame_time if last_frame_time is not None else args.first
      with open(image_name, 'wb') as frame_image:
        frame_image.write(b64decode(f.data))
      frames_list.write("file '{}'\nduration {}\n".format(image_name.split('/')[-1], frame_duration))
      if i == len(frames):
        frames_list.write("file '{}'\n".format(image_name.split('/')[-1]))
      i += 1
      last_frame_time = f.metadata.timestamp

def make_mp4():
  if args.output is None:
    vid_name = '{}-{}'.format(urlsplit(args.url).netloc,
                                time.strftime('%Y%m%d_%H%M%S'))
  else:
    vid_name = args.output
  subprocess.run(['ffmpeg', '-y', '-f', 'concat',
                  '-i', '/tmp/frames.txt',
                  '-vf', 'fps={}'.format(args.fps),
                  '-pix_fmt', 'yuv420p',
                  '-c:v', 'libx264',
                  '{}/{}.mp4'.format(args.dir, vid_name)])

async def main():

  ws_debugger_url = get_ws_debugger_url(args.cdb_host_port)
  logger.info('Connecting to browser: %s', ws_debugger_url)
 
  async with open_cdp(ws_debugger_url) as conn:
    logger.info('Listing targets')
    targets = await target.get_targets()

    for t in targets:
      if ( t.type_ == 'page' and
           not t.url.startswith('devtools://') and
           not t.attached
         ):
        target_id = t.target_id
        break

    logger.info('Attaching to target id=%s', target_id)
    async with conn.open_session(target_id) as session:

      logger.info('Setting device emulation')
      await emulation.set_device_metrics_override(
          width=args.width, height=args.height, device_scale_factor=1, mobile=False
      )

      logger.info('Enabling page events')
      await page.enable()

      await capture_screencast(session)

    write_frames(frames)
    make_mp4()

if __name__ == '__main__':
  global args
  args = parse_args()
  logger.info('ARGS: {}'.format(args))
  trio.run(main, restrict_keyboard_interrupt_to_checkpoints=True)
