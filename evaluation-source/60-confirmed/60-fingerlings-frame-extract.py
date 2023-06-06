import cv2
import os

# Read the video from specified path
vid = cv2.VideoCapture(
    "C:/Users/Christian/Downloads/for-test-dataset/60-confirmed-fingerlings.mp4")

try:
    # Creating a folder named data
    if not os.path.exists('data'):
        os.makedirs('data')
except OSError:
    print('Error: Creating directory of data')

# Frame and interval
current_frame = 0
frame_interval = 65
while True:
    # Reading from frame
    success, frame = vid.read()

    if success:
        # Check if current frame number is a multiple of the interval
        if current_frame % frame_interval == 0:
            # Continue creating images until video remains
            name = './data/frame' + str(current_frame) + '.jpg'
            print('Creating...' + name)

            # Writing the extracted images
            cv2.imwrite(name, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

        # Increasing counter to show how many frames are created
        current_frame += 1
    else:
        break

# Release all space and windows once done
vid.release()
cv2.destroyAllWindows()
