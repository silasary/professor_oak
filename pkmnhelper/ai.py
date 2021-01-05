import asyncio
import os
import aiohttp
from fastai.vision import load_learner, open_image

export_file_url = r"https://is.gd/flgMdy"
export_file_name = 'pokemon_resnet18_73acc.pkl'

async def download_file():
    dest = os.path.join('model', export_file_name)
    if os.path.exists(dest):
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(export_file_url) as response:
            data = await response.read()
            with open(dest, 'wb') as f:
                f.write(data)

def setup_learner():
    asyncio.get_event_loop().run_until_complete(asyncio.ensure_future(download_file()))
    try:
        learn = load_learner('model/', export_file_name)
        return learn.to_fp32()
    except RuntimeError as e:
        if len(e.args) > 0 and 'CPU-only machine' in e.args[0]:
            print(e)
            message = "\n\nThis model was trained with an old version of fastai and will not work in a CPU environment.\n\nPlease update the fastai library in your training environment and export your model again.\n\nSee instructions for 'Returning to work' at https://course.fast.ai."
            raise RuntimeError(message)
        else:
            raise

AI = setup_learner()

def predict(fname) -> str:
    fimg = open_image(fname)
    return str(AI.predict(fimg)[0])