import asyncio
import aiohttp
import io
import cv2
import numpy as np
from sanic import Sanic, response, request as sanic_request

app = Sanic(__name__)

# Define the external API URL
external_api_url = "https://api.slingacademy.com/v1/sample-data/photos"

# Define the dimensions for the composite image
thumbnail_size = (32, 32)
num_images = 132
images_per_row = 10  # Number of images to display in each row

# Function to fetch and process an image from the API
async def fetch_and_process_image(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                # Read the image content
                image_bytes = await response.read()

                # Convert image bytes to numpy array
                image_data = np.frombuffer(image_bytes, np.uint8)

                # Decode the image using OpenCV
                image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

                # Resize the image to the specified thumbnail size
                image_thumbnail = cv2.resize(image, thumbnail_size)

                return image_thumbnail
            else:
                # Return a black image tile in case of fetching error
                return np.zeros((thumbnail_size[1], thumbnail_size[0], 3), np.uint8)
    except Exception as e:
        # Return a blue image tile in case of any error (e.g., image decode error)
        return np.full((thumbnail_size[1], thumbnail_size[0], 3), (0, 0, 255), np.uint8)

# Function to fetch the image URLs from the API with optional limit and offset
async def fetch_image_urls(session, limit=10, offset=0):
    try:
        params = {'limit': limit, 'offset': offset}
        async with session.get(external_api_url, params=params) as response:
            if response.status == 200:
                # Read the JSON response
                data = await response.json()

                # Extract the 'photos' array from the JSON response
                photos = data.get('photos', [])

                # Extract image URLs from photo objects
                image_urls = [photo['url'] for photo in photos]

                return image_urls
            else:
                # Return an empty list in case of fetching error
                return []
    except Exception as e:
        # Return an empty list in case of any error
        return []

# Function to create the composite image
async def create_composite_image(limit=10, offset=0):
    async with aiohttp.ClientSession() as session:
        image_urls = await fetch_image_urls(session, limit, offset)
        tasks = []

        for url in image_urls:
            tasks.append(fetch_and_process_image(session, url))

        images = await asyncio.gather(*tasks)

        # Calculate the dimensions of the composite image based on the number of images and images per row
        num_rows = len(images) // images_per_row

        # Create a list of rows for the composite image
        rows = []

        for i in range(num_rows):
            row_images = images[i * images_per_row : (i + 1) * images_per_row]
            row_image = np.hstack(row_images)
            rows.append(row_image)

        # Create the composite image by stacking rows vertically
        composite_image = np.vstack(rows)

        return composite_image

@app.route('/')
async def serve_composite_image(request: sanic_request):
    # Get the limit and offset query parameters from the request
    limit = request.args.get('limit', num_images)
    offset = request.args.get('offset', 0)

    # Create the composite image with optional limit and offset
    composite_image = await create_composite_image(limit, offset)

    # Convert the composite image to bytes
    _, image_bytes = cv2.imencode('.jpeg', composite_image)

    # Serve the composite image as a response
    return response.raw(image_bytes.tobytes(), content_type='image/jpeg')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)