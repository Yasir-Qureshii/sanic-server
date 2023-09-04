import asyncio
import aiohttp
import io
from sanic import Sanic, response, request as sanic_request
from PIL import Image, ImageOps

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

                # Open the image using Pillow
                image = Image.open(io.BytesIO(image_bytes))

                # Resize the image to the specified thumbnail size with antialiasing
                image_thumbnail = ImageOps.fit(image, thumbnail_size, method=0, bleed=0.0, centering=(0.5, 0.5))

                return image_thumbnail
            else:
                # Return a black image tile in case of fetching error
                return Image.new("RGB", thumbnail_size, (0, 0, 0))
    except Exception as e:
        # Return a blue image tile in case of any error (e.g., image decode error)
        return Image.new("RGB", thumbnail_size, (0, 0, 255))

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
            row_image = Image.new("RGB", (thumbnail_size[0] * images_per_row, thumbnail_size[1]))
            for j, image in enumerate(row_images):
                row_image.paste(image, (j * thumbnail_size[0], 0))
            rows.append(row_image)

        # Create the composite image by stacking rows vertically
        composite_image = Image.new("RGB", (thumbnail_size[0] * images_per_row, thumbnail_size[1] * num_rows))
        for i, row in enumerate(rows):
            composite_image.paste(row, (0, i * thumbnail_size[1]))

        return composite_image

@app.route('/')
async def serve_composite_image(request: sanic_request):
    # Get the limit and offset query parameters from the request
    limit = request.args.get('limit', 10)
    offset = request.args.get('offset', 0)

    # Create the composite image with optional limit and offset
    composite_image = await create_composite_image(limit, offset)

    # Convert the composite image to bytes
    with io.BytesIO() as output_buffer:
        composite_image.save(output_buffer, format="JPEG")
        image_bytes = output_buffer.getvalue()

    # Serve the composite image as a response
    return response.raw(image_bytes, content_type='image/jpeg')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
