# YOLOv5 🚀 by Ultralytics, GPL-3.0 license
"""
Run YOLOv5 segmentation inference on images, videos, directories, streams, etc.

Usage - sources:
    $ python segment/predict.py --weights yolov5s-seg.pt --source 0                               # webcam
                                                                  img.jpg                         # image
                                                                  vid.mp4                         # video
                                                                  path/                           # directory
                                                                  'path/*.jpg'                    # glob
                                                                  'https://youtu.be/Zgi9g1ksQHc'  # YouTube
                                                                  'rtsp://example.com/media.mp4'  # RTSP, RTMP, HTTP stream

Usage - formats:
    $ python segment/predict.py --weights yolov5s-seg.pt                 # PyTorch
                                          yolov5s-seg.torchscript        # TorchScript
                                          yolov5s-seg.onnx               # ONNX Runtime or OpenCV DNN with --dnn
                                          yolov5s-seg.xml                # OpenVINO
                                          yolov5s-seg.engine             # TensorRT
                                          yolov5s-seg.mlmodel            # CoreML (macOS-only)
                                          yolov5s-seg_saved_model        # TensorFlow SavedModel
                                          yolov5s-seg.pb                 # TensorFlow GraphDef
                                          yolov5s-seg.tflite             # TensorFlow Lite
                                          yolov5s-seg_edgetpu.tflite     # TensorFlow Edge TPU
"""

import argparse
import os
import platform
import sys
import collections
import cv2
import numpy as np
from google.colab.patches import cv2_imshow
from pathlib import Path
from collections import Counter

import torch
import torch.backends.cudnn as cudnn

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # YOLOv5 root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # add ROOT to PATH
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))  # relative

from models.common import DetectMultiBackend
from utils.dataloaders import IMG_FORMATS, VID_FORMATS, LoadImages, LoadStreams
from utils.general import (LOGGER, Profile, check_file, check_img_size, check_imshow, check_requirements, colorstr, cv2,
                           increment_path, non_max_suppression, print_args, scale_coords, strip_optimizer, xyxy2xywh)
from utils.plots import Annotator, colors, save_one_box
from utils.segment.general import process_mask, scale_masks
from utils.segment.plots import plot_masks
from utils.torch_utils import select_device, smart_inference_mode

def count(found_classes,im0): #March 8, 2023: Implementing the count function
    aligns=im0.shape
    align_bottom=aligns[0]
    align_right=(aligns[1]/12) 

    for i, (k, v) in enumerate(found_classes.items()):
        a=f"Real-time milkfish {k}s count: {v}"
        align_bottom=align_bottom-650
        cv2.putText(im0, str(a), (int(align_right),align_bottom), cv2.FONT_HERSHEY_SIMPLEX, 1,(0,0,0),1,cv2.LINE_AA)
        # cv2.putText(im0, str(a), (int(align_right),align_bottom), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1,(0,0,0),1,cv2.LINE_AA)

@smart_inference_mode()
def run(
        weights=ROOT / 'yolov5s-seg.pt',  # model.pt path(s)
        source=ROOT / 'data/images',  # file/dir/URL/glob, 0 for webcam
        data=ROOT / 'data/coco128.yaml',  # dataset.yaml path
        imgsz=(640, 640),  # inference size (height, width)
        conf_thres=0.25,  # confidence threshold
        iou_thres=0.45,  # NMS IOU threshold
        max_det=1000,  # maximum detections per image
        device='',  # cuda device, i.e. 0 or 0,1,2,3 or cpu
        view_img=False,  # show results
        save_txt=False,  # save results to *.txt
        save_conf=False,  # save confidences in --save-txt labels
        save_crop=False,  # save cropped prediction boxes
        nosave=False,  # do not save images/videos
        classes=None,  # filter by class: --class 0, or --class 0 2 3
        agnostic_nms=False,  # class-agnostic NMS
        augment=False,  # augmented inference
        visualize=False,  # visualize features
        update=False,  # update all models
        project=ROOT / 'runs/predict-seg',  # save results to project/name
        name='exp',  # save results to project/name
        exist_ok=False,  # existing project/name ok, do not increment
        line_thickness=3,  # bounding box thickness (pixels)
        hide_labels=False,  # hide labels
        hide_conf=False,  # hide confidences
        half=False,  # use FP16 half-precision inference
        dnn=False,  # use OpenCV DNN for ONNX inference
):

    source = str(source)
    save_img = not nosave and not source.endswith('.txt')  # save inference images
    is_file = Path(source).suffix[1:] in (IMG_FORMATS + VID_FORMATS)
    is_url = source.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://'))
    webcam = source.isnumeric() or source.endswith('.txt') or (is_url and not is_file)
    if is_url and is_file:
        source = check_file(source)  # download

    # Directories
    save_dir = increment_path(Path(project) / name, exist_ok=exist_ok)  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Load model
    device = select_device(device)
    model = DetectMultiBackend(weights, device=device, dnn=dnn, data=data, fp16=half)
    stride, names, pt = model.stride, model.names, model.pt
    imgsz = check_img_size(imgsz, s=stride)  # check image size

    # Dataloader
    if webcam:
        view_img = check_imshow()
        cudnn.benchmark = True  # set True to speed up constant image size inference
        dataset = LoadStreams(source, img_size=imgsz, stride=stride, auto=pt)
        bs = len(dataset)  # batch_size
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride, auto=pt)
        bs = 1  # batch_size
    vid_path, vid_writer = [None] * bs, [None] * bs

    # Run inference
    det_lengths = []   #Added March 6, 2023 12:08 AM: All the count in frames will be saved here and the most repeated count will be printed in the last part.
    found_classes={} # Creating a dictionary to store the detected instance
    model.warmup(imgsz=(1 if pt else bs, 3, *imgsz))  # warmup
    seen, windows, dt = 0, [], (Profile(), Profile(), Profile())
    for path, im, im0s, vid_cap, s in dataset:
        with dt[0]:
            im = torch.from_numpy(im).to(device)
            im = im.half() if model.fp16 else im.float()  # uint8 to fp16/32
            im /= 255  # 0 - 255 to 0.0 - 1.0
            if len(im.shape) == 3:
                im = im[None]  # expand for batch dim

        # Inference
        with dt[1]:
            visualize = increment_path(save_dir / Path(path).stem, mkdir=True) if visualize else False
            pred, out = model(im, augment=augment, visualize=visualize)
            proto = out[1]

        # NMS
        with dt[2]:
            pred = non_max_suppression(pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det, nm=32)

        # Second-stage classifier (optional)
        # pred = utils.general.apply_classifier(pred, classifier_model, im, im0s)

        # Process predictions
        for i, det in enumerate(pred):  # per image
            seen += 1
            if webcam:  # batch_size >= 1
                p, im0, frame = path[i], im0s[i].copy(), dataset.count
                s += f'{i}: '
            else:
                p, im0, frame = path, im0s.copy(), getattr(dataset, 'frame', 0)

            p = Path(p)  # to Path
            save_path = str(save_dir / p.name)  # im.jpg
            txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'image' else f'_{frame}')  # im.txt
            s += '%gx%g ' % im.shape[2:]  # print string
            gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
            imc = im0.copy() if save_crop else im0  # for save_crop
            annotator = Annotator(im0, line_width=line_thickness, example=str(names))
            if len(det):
                masks = process_mask(proto[i], det[:, 6:], det[:, :4], im.shape[2:], upsample=True)  # HWC

                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(im.shape[2:], det[:, :4], im0.shape).round()



                # Print results
                for c in det[:, 5].unique():
                    n = (det[:, 5] == c).sum()  # detections per class
                    class_index=int(c)
                    count_of_object=int(n)

                    found_classes[names[class_index]]=int(n)

                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string
                    det_lengths.append(len(det)) #append count to det_lengths 
                    
                # Mask plotting ----------------------------------------------------------------------------------------
                mcolors = [colors(int(cls), True) for cls in det[:, 5]]
                im_masks = plot_masks(im[i], masks, mcolors)  # image with masks shape(imh,imw,3)
                annotator.im = scale_masks(im.shape[2:], im_masks, im0.shape)  # scale to original h, w
                # Mask plotting ----------------------------------------------------------------------------------------

                # # Write results
                # for *xyxy, conf, cls in reversed(det[:, :6]):
                #     if save_txt:  # Write to file
                #         xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                #         line = (cls, *xywh, conf) if save_conf else (cls, *xywh)  # label format
                #         with open(f'{txt_path}.txt', 'a') as f:
                #             f.write(('%g ' * len(line)).rstrip() % line + '\n')

                #     if save_img or save_crop or view_img:  # Add bbox to image
                #         # count_accuracy = (most_common_count/len(det_lengths))*100
                #         c = int(cls)  # integer class
                #         # label = None if hide_labels else (names[c] if hide_conf else f'{conf:.2f}% milkfish {names[c]} | Real-Time Count: {len(det)}')
                #         label = None if hide_labels else (names[c] if hide_conf else f'{len(det)}')
                #         # label = None if hide_labels else (f'Real-Time Count: {len(det)} {names[c]}s {count_accuracy}' if hide_conf else f'Real-Time Count: {len(det)} {names[c]}s {conf:.2f}%')
                #         annotator.box_label(xyxy, label, color=colors(c, True))
                #         # Source:  https://medium.com/@dogankeskin01/yolov7-object-counter-logic-14e547f9a0b6

                #     if save_crop:
                #         # Source:  https://medium.com/@dogankeskin01/yolov7-object-counter-logic-14e547f9a0b6
                #         # cv2.putText(im0, f"Real-Time Count: {len(det)}", (10, 105), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 0), 1)
                #         # cv2.putText(im0, f"{s}", (10, 105), cv2.FONT_HERSHEY_TRIPLEX, 1, (255, 0, 0), 1)
                #         save_one_box(xyxy, imc, file=save_dir / 'crops' / names[c] / f'{p.stem}.jpg', BGR=True)

            # Stream results
            im0 = annotator.result()
            if view_img:
                if platform.system() == 'Linux' and p not in windows:
                    windows.append(p)
                    cv2.namedWindow(str(p), cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)  # allow window resize (Linux)
                    cv2.resizeWindow(str(p), im0.shape[1], im0.shape[0])
                cv2.imshow(str(p), im0)
                cv2.waitKey(1)  # 1 millisecond

            # Save results (image with detections)
            if save_img:
                count(found_classes=found_classes,im0=im0) #March 8, 2023: Applying counter function
                if dataset.mode == 'image':
                    # cv2.putText(im0, f"Real-Time Count: {len(det)}", (10, 105), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 255, 0), 1)
                    # # cv2.putText(im0, f"{s}", (10, 205), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 255, 0), 1)
                    # count(found_classes=found_classes,im0=im0) #March 8, 2023: Applying counter function
                    cv2.imwrite(save_path, im0)
                else:  # 'video' or 'stream'
                    if vid_path[i] != save_path:  # new video
                        vid_path[i] = save_path
                        if isinstance(vid_writer[i], cv2.VideoWriter):
                            # count(found_classes=found_classes,im0=im0) #March 8, 2023: Applying counter function
                            vid_writer[i].release()  # release previous video writer
                        if vid_cap:  # video
                            fps = vid_cap.get(cv2.CAP_PROP_FPS)
                            w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        else:  # stream
                            fps, w, h = 30, im0.shape[1], im0.shape[0]
                        save_path = str(Path(save_path).with_suffix('.mp4'))  # force *.mp4 suffix on results videos
                        # count(found_classes=found_classes,im0=im0) #March 8, 2023: Applying counter function
                        vid_writer[i] = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                    vid_writer[i].write(im0)

        # Print time (inference-only)
        LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")

    # Print results
    t = tuple(x.t / seen * 1E3 for x in dt)  # speeds per image
    LOGGER.info(f'Speed: %.1fms pre-process, %.1fms inference, %.1fms NMS per image at shape {(1, 3, *imgsz)}' % t)
    if save_txt or save_img:
        s = f"\n{len(list(save_dir.glob('labels/*.txt')))} labels saved to {save_dir / 'labels'}" if save_txt else ''
        LOGGER.info(f"Results saved to {colorstr('bold', save_dir)}{s}")
    if update:
        strip_optimizer(weights[0])  # update model (to fix SourceChangeWarning)
    
    
    most_common_length = Counter(det_lengths).most_common(1)[0][0] #most_common_length = Counter(det_lengths).most_common(1)[0][0]: This line calculates the most common length of the detections by first creating a Counter object from the det_lengths list using the Counter() function. The most_common() function is then called on the Counter object with an argument of 1, which returns a list of tuples where the first item in each tuple is the most common length of detections and the second item is the count of that length. The [0][0] indexing is used to extract the most common length of detections from the first tuple.
    print("\nResults of the milkfish fingerlings counting:")
    # print("    • Most Repeated Count of the Detected Fingerlings:", most_common_length) 
    print("    • Most Repeated Count:", most_common_length) 

    # Define the true count
    true_count = 9
    # Define the ten predicted counts
    #det_lengths: List containing the count of fingerlings per frames
    # Calculate the accuracy of each prediction as a percentage
    accuracies = [100 * (1 - abs(det_length - true_count) / true_count) for det_length in det_lengths]
    # Calculate the average accuracy
    average_accuracy = sum(accuracies) / len(accuracies)
    # Print the average accuracy as a percentage
    print(f"    • Average Accuracy: {average_accuracy:.2f}%")

    # most_common_count = Counter(det_lengths).get(most_common_length)
    # # print("    • Total Repeatition of the Most Repeated Count of Fingerlings:", most_common_count, "out of", len(det_lengths))
    # print("    • Total Repeatition:", most_common_count, "out of", len(det_lengths))
    # print("    • Count Accuracy = (Model Count Prediction / Count Confirmed by the Farmer) * 100):", (most_common_count/len(det_lengths))*100, "%")




def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default=ROOT / 'yolov5s-seg.pt', help='model path(s)')
    parser.add_argument('--source', type=str, default=ROOT / 'data/images', help='file/dir/URL/glob, 0 for webcam')
    parser.add_argument('--data', type=str, default=ROOT / 'data/coco128.yaml', help='(optional) dataset.yaml path')
    parser.add_argument('--imgsz', '--img', '--img-size', nargs='+', type=int, default=[640], help='inference size h,w')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='NMS IoU threshold')
    parser.add_argument('--max-det', type=int, default=1000, help='maximum detections per image')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='show results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--save-crop', action='store_true', help='save cropped prediction boxes')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --classes 0, or --classes 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--visualize', action='store_true', help='visualize features')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default=ROOT / 'runs/predict-seg', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--line-thickness', default=3, type=int, help='bounding box thickness (pixels)')
    parser.add_argument('--hide-labels', default=False, action='store_true', help='hide labels')
    parser.add_argument('--hide-conf', default=False, action='store_true', help='hide confidences')
    parser.add_argument('--half', action='store_true', help='use FP16 half-precision inference')
    parser.add_argument('--dnn', action='store_true', help='use OpenCV DNN for ONNX inference')
    opt = parser.parse_args()
    opt.imgsz *= 2 if len(opt.imgsz) == 1 else 1  # expand
    print_args(vars(opt))
    return opt


def main(opt):
    check_requirements(exclude=('tensorboard', 'thop'))
    run(**vars(opt))


if __name__ == "__main__":
    opt = parse_opt()
    main(opt)
