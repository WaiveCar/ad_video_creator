'''
Make a screenshot of a target web page.

To use this example, start Chrome (or any other browser that supports CDP) with
the option `--remote-debugging-port=9000`. The URL that Chrome is listening on
is displayed in the terminal after Chrome starts up.

Then run this script with the Chrome URL as the first argument and the target
website URL as the second argument:

$ python examples/screenshot.py \
    ws://localhost:9000/devtools/browser/facfb2295-... \
    https://www.hyperiongray.com
'''
from base64 import b64decode
import logging
import os
import sys
import subprocess

import requests
import trio
from trio_cdp import open_cdp, emulation, page, target


log_level = os.environ.get('LOG_LEVEL', 'info').upper()
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger('screenshot')
logging.getLogger('trio-websocket').setLevel(logging.WARNING)

def get_ws_debugger_url(host_and_port):
  r = requests.get('http://{}/json/version'.format(host_and_port))
  j = r.json()
  return j.get('webSocketDebuggerUrl')

async def capture_screencast(session):
  global frames

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
    page_reloaded = False
    async for sc_data in session.listen(page.ScreencastFrame):
      if not page_reloaded:
        await page.reload()
        page_reloaded = True
        continue
      #err_data = sc_data
      frames.append(sc_data)
      logger.info('Saved frame to memory')
      await page.screencast_frame_ack(sc_data.session_id)
    
  logger.info('Starting Screencast')
  await page.start_screencast(format_='png', every_nth_frame=1)
  async with trio.open_nursery() as nursery:
    nursery.start_soon(wait_for_page_load, nursery.cancel_scope)
    nursery.start_soon(frame_saver)

def save_frames(frames):
  i = 0
  last_frame_time = None
  with open('/tmp/frames.txt', 'w') as frames_list:
    for f in frames:
      image_name = '/tmp/frame-{:02}.png'.format(i)
      frame_duration = f.metadata.timestamp - last_frame_time if last_frame_time is not None else 1/60
      with open(image_name, 'wb') as frame_image:
        frame_image.write(b64decode(f.data))
      frames_list.write("file '{}'\nduration {}\n".format(image_name.split('/')[-1], frame_duration))
      i += 1
      last_frame_time = f.metadata.timestamp

def make_mp4():
  subprocess.run(['ffmpeg', '-y', '-f', 'concat',
                  '-i', '/tmp/frames.txt',
                  '-vf', 'fps=60',
                  '-c:v', 'libx264',
                  '-pix_fmt', 'yuv420p',
                  'output/video.mp4'])

async def main():
  global err_data, ack_data, frames
  frames = []

  ws_debugger_url = get_ws_debugger_url(sys.argv[1])
  logger.info('Connecting to browser: %s', ws_debugger_url)
 
  async with open_cdp(ws_debugger_url) as conn:
    logger.info('Listing targets')
    targets = await target.get_targets()

    for t in targets:
      try:
        if (t.type_ == 'page' and
          not t.url.startswith('devtools://') and
          not t.attached):
          target_id = t.target_id
          break
      except:
        global error_t
        error_t = targets
        raise

    logger.info('Attaching to target id=%s', target_id)
    async with conn.open_session(target_id) as session:

      logger.info('Setting device emulation')
      await emulation.set_device_metrics_override(
          width=1920, height=1080, device_scale_factor=1, mobile=False
      )

      logger.info('Enabling page events')
      await page.enable()

      logger.info('Navigating to %s', sys.argv[2])
      async with session.wait_for(page.LoadEventFired):
          await page.navigate(url=sys.argv[2])

      await capture_screencast(session)

    save_frames(frames)
    make_mp4()

if __name__ == '__main__':
  if len(sys.argv) != 3:
    sys.stderr.write('Usage: screenshot.py <host:port> <target url>')
    sys.exit(1)
  trio.run(main, restrict_keyboard_interrupt_to_checkpoints=True)
