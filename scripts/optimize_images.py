#!/usr/bin/env python3
"""
이미지 최적화 스크립트
60 Leaders 프로필 이미지 및 썸네일 최적화
"""
import os
import sys
from pathlib import Path
from PIL import Image
import argparse


def optimize_image(
    input_path: str,
    output_path: str,
    size: int = 1200,
    quality: int = 85,
    suffix: str = ""
):
    """
    이미지 최적화 및 리사이즈

    Args:
        input_path: 입력 이미지 경로
        output_path: 출력 디렉토리 경로
        size: 출력 크기 (정사각형)
        quality: JPEG 품질 (1-100)
        suffix: 파일명 접미사 (예: "thumb")
    """
    try:
        # 이미지 열기
        with Image.open(input_path) as img:
            # RGB 변환 (RGBA, P 등 처리)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # 리사이즈 (정사각형, 중앙 크롭)
            # 1. 짧은 쪽을 size에 맞춤
            aspect_ratio = img.width / img.height
            if aspect_ratio > 1:
                new_width = int(size * aspect_ratio)
                new_height = size
            else:
                new_width = size
                new_height = int(size / aspect_ratio)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 2. 중앙 크롭
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            right = left + size
            bottom = top + size
            img = img.crop((left, top, right, bottom))

            # 출력 파일명 생성
            input_file = Path(input_path)
            if suffix:
                output_filename = f"{input_file.stem}-{suffix}{input_file.suffix}"
            else:
                output_filename = input_file.name

            output_filepath = Path(output_path) / output_filename

            # 저장
            img.save(
                output_filepath,
                format='JPEG',
                quality=quality,
                optimize=True
            )

            # 파일 크기 확인
            input_size = os.path.getsize(input_path) / 1024  # KB
            output_size = os.path.getsize(output_filepath) / 1024  # KB
            reduction = ((input_size - output_size) / input_size * 100) if input_size > 0 else 0

            print(f"✅ {input_file.name}")
            print(f"   크기: {size}x{size}px")
            print(f"   품질: {quality}%")
            print(f"   용량: {input_size:.1f}KB → {output_size:.1f}KB (-{reduction:.1f}%)")
            print()

            return True

    except Exception as e:
        print(f"❌ 오류: {input_path}")
        print(f"   {str(e)}")
        print()
        return False


def optimize_directory(
    input_dir: str,
    output_dir: str,
    size: int = 1200,
    quality: int = 85,
    suffix: str = ""
):
    """
    디렉토리 내 모든 이미지 최적화

    Args:
        input_dir: 입력 디렉토리
        output_dir: 출력 디렉토리
        size: 출력 크기
        quality: JPEG 품질
        suffix: 파일명 접미사
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # 출력 디렉토리 생성
    output_path.mkdir(parents=True, exist_ok=True)

    # 지원 포맷
    supported_formats = {'.jpg', '.jpeg', '.png', '.webp'}

    # 이미지 파일 찾기
    image_files = [
        f for f in input_path.iterdir()
        if f.is_file() and f.suffix.lower() in supported_formats
    ]

    if not image_files:
        print(f"⚠️  이미지 파일을 찾을 수 없습니다: {input_dir}")
        return

    print(f"🖼️  총 {len(image_files)}개 이미지 최적화 시작\n")
    print(f"입력: {input_dir}")
    print(f"출력: {output_dir}")
    print(f"크기: {size}x{size}px")
    print(f"품질: {quality}%")
    print(f"접미사: {suffix or '없음'}")
    print(f"{'='*60}\n")

    success_count = 0
    for image_file in image_files:
        if optimize_image(
            str(image_file),
            str(output_path),
            size,
            quality,
            suffix
        ):
            success_count += 1

    print(f"{'='*60}")
    print(f"✅ 완료: {success_count}/{len(image_files)} 성공")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='60 Leaders 이미지 최적화 스크립트'
    )
    parser.add_argument(
        '--input',
        '-i',
        required=True,
        help='입력 디렉토리 또는 파일 경로'
    )
    parser.add_argument(
        '--output',
        '-o',
        required=True,
        help='출력 디렉토리 경로'
    )
    parser.add_argument(
        '--size',
        '-s',
        type=int,
        default=1200,
        help='출력 크기 (정사각형, 기본값: 1200)'
    )
    parser.add_argument(
        '--quality',
        '-q',
        type=int,
        default=85,
        help='JPEG 품질 (1-100, 기본값: 85)'
    )
    parser.add_argument(
        '--suffix',
        default='',
        help='파일명 접미사 (예: thumb)'
    )

    args = parser.parse_args()

    # 입력 검증
    if not os.path.exists(args.input):
        print(f"❌ 오류: 입력 경로를 찾을 수 없습니다: {args.input}")
        sys.exit(1)

    if args.quality < 1 or args.quality > 100:
        print(f"❌ 오류: 품질은 1-100 사이여야 합니다: {args.quality}")
        sys.exit(1)

    # 디렉토리 처리
    if os.path.isdir(args.input):
        optimize_directory(
            args.input,
            args.output,
            args.size,
            args.quality,
            args.suffix
        )
    # 단일 파일 처리
    else:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        optimize_image(
            args.input,
            str(output_dir),
            args.size,
            args.quality,
            args.suffix
        )


if __name__ == '__main__':
    main()
