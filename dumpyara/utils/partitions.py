#
# Copyright (C) 2022 Dumpyara Project
#
# SPDX-License-Identifier: GPL-3.0
#

from pathlib import Path
from sebaubuntu_libs.libexception import format_exception
from sebaubuntu_libs.liblogging import LOGE, LOGI
from sebaubuntu_libs.libstring import removesuffix
from shutil import copyfile, move
from subprocess import CalledProcessError
from typing import List

from dumpyara.lib.libsevenz import sevenz
from dumpyara.utils.bootimg import extract_bootimg
from dumpyara.utils.raw_image import get_raw_image

(
	FILESYSTEM,
	BOOTIMAGE,
	RAW,
) = range(3)

# partition: type
# Please document partition where possible
PARTITIONS = {
	# Bootloader/raw images
	## AOSP
	"boot": BOOTIMAGE,
	"dtbo": RAW,
	"recovery": BOOTIMAGE,
	"vendor_boot": BOOTIMAGE,

	## SoC vendor/OEM/ODM
	"exaid": BOOTIMAGE,
	"rescue": BOOTIMAGE,
	"tz": RAW,

	# Partitions with a standard filesystem
	## AOSP
	"odm": FILESYSTEM,
	"odm_dlkm": FILESYSTEM,
	"oem": FILESYSTEM,
	"product": FILESYSTEM,
	"system": FILESYSTEM,
	"system_dlkm": FILESYSTEM,
	"system_ext": FILESYSTEM,
	"system_other": FILESYSTEM,
	"vendor": FILESYSTEM,
	"vendor_dlkm": FILESYSTEM,

	## SoC vendor/OEM/ODM
	"cust": FILESYSTEM,
	"factory": FILESYSTEM,
	"india": FILESYSTEM,
	"modem": FILESYSTEM,
	"my_bigball": FILESYSTEM,
	"my_carrier": FILESYSTEM,
	"my_company": FILESYSTEM,
	"my_country": FILESYSTEM,
	"my_custom": FILESYSTEM,
	"my_engineering": FILESYSTEM,
	"my_heytap": FILESYSTEM,
	"my_manifest": FILESYSTEM,
	"my_odm": FILESYSTEM,
	"my_operator": FILESYSTEM,
	"my_preload": FILESYSTEM,
	"my_product": FILESYSTEM,
	"my_region": FILESYSTEM,
	"my_stock": FILESYSTEM,
	"my_version": FILESYSTEM,
	"odm_ext": FILESYSTEM,
	"oppo_product": FILESYSTEM,
	"opproduct": FILESYSTEM,
	"preload_common": FILESYSTEM,
	"reserve": FILESYSTEM,
	"special_preload": FILESYSTEM,
	"systemex": FILESYSTEM,
	"xrom": FILESYSTEM,
}

# alternative name: generic name
ALTERNATIVE_PARTITION_NAMES = {
	"boot-verified": "boot",
	"dtbo-verified": "dtbo",
	"NON-HLOS": "modem",
}

def get_partition_name(partition_name: str):
	"""Get the unaliased partition name."""
	return ALTERNATIVE_PARTITION_NAMES.get(partition_name, partition_name)

def get_partition_names():
	"""Get a list of partition names."""
	return list(PARTITIONS)

def get_partition_names_with_alias():
	"""Get a list of partition names with alias."""
	return get_partition_names() + list(ALTERNATIVE_PARTITION_NAMES)

def get_partition_names_with_ab():
	"""Get a list of partition names with A/B variants.

	This is used during step 2 to also extract the A/B partitions."""
	partitions: List[str] = []

	for partition in get_partition_names_with_alias():
		partitions.append(partition)
		partitions.append(f"{partition}_a")
		partitions.append(f"{partition}_b")

	return partitions

def prepare_raw_images(files_path: Path, raw_images_path: Path):
	"""Prepare raw images for 7z extraction."""
	for partition_name in get_partition_names_with_ab():
		partition_output = raw_images_path / f"{partition_name}.img"

		get_raw_image(partition_name, files_path, partition_output)

def fix_aliases(images_path: Path):
	"""Move aliased partitions to their generic name."""
	for alt_name, name in ALTERNATIVE_PARTITION_NAMES.items():
		alt_path = images_path / f"{alt_name}.img"
		partition_path = images_path / f"{name}.img"

		if not alt_path.exists():
			continue

		if partition_path.exists():
			LOGI(f"Ignoring {alt_name} ({name} already extracted)")
			alt_path.unlink()

		LOGI(f"Fixing alias {alt_name} -> {name}")
		move(alt_path, partition_path)

def extract_partitions(raw_images_path: Path, output_path: Path):
	"""Extract partition files from raw images."""
	# At this point aliases shouldn't be used anymore
	for partition in get_partition_names():
		partition_type = PARTITIONS[partition]

		image_path = raw_images_path / f"{partition}.img"
		if not image_path.exists():
			continue

		LOGI(f"Extracting {partition}")

		if partition_type == BOOTIMAGE:
			try:
				extract_bootimg(image_path, output_path / partition)
			except Exception as e:
				LOGE(f"Failed to extract {image_path.name}")
				LOGE(f"{format_exception(e)}")
		elif partition_type == FILESYSTEM:
			try:
				sevenz(f'x {image_path} -y -o"{output_path / partition}"/')
			except CalledProcessError as e:
				LOGE(f"Error extracting {image_path.name}")
				LOGE(f"{e.output.decode('UTF-8', errors='ignore')}")

		if partition_type in (RAW, BOOTIMAGE):
			copyfile(image_path, output_path / f"{partition}.img", follow_symlinks=True)

def get_filename_suffixes(file: Path):
	return "".join(file.suffixes)

def get_filename_without_extensions(file: Path):
	return removesuffix(str(file.name), get_filename_suffixes(file))

def correct_ab_filenames(images_path: Path):
	partitions = get_partition_names_with_alias()
	for file in images_path.iterdir():
		if not file.is_file():
			LOGI(f"correct_ab_filenames: {file} doesn't exist, skipping")
			continue

		file_stem = get_filename_without_extensions(file)
		LOGI(f"correct_ab_filenames: file: {file}, file_stem: {file_stem}")

		if not file_stem.endswith("_a") and not file_stem.endswith("_b"):
			LOGI(f"correct_ab_filenames: file_stem doesn't end with a suffix, skipping")
			continue

		suffix = file_stem[-2:]
		file_stem_unslotted = removesuffix(file_stem, suffix)

		if file_stem_unslotted not in partitions:
			LOGI(f"correct_ab_filenames: file_stem_unslotted {file_stem_unslotted} not in the list of known partitions, skipping")
			continue

		non_ab_partition_path = images_path / f"{file_stem_unslotted}{get_filename_suffixes(file)}"
		a_partition_path = images_path / f"{file_stem_unslotted}_a{get_filename_suffixes(file)}"
		b_partition_path = images_path / f"{file_stem_unslotted}_b{get_filename_suffixes(file)}"

		if non_ab_partition_path.is_file():
			LOGI(f"correct_ab_filenames: {non_ab_partition_path} already exists, skipping")
			file.unlink()
			continue

		if a_partition_path.is_file():
			move(a_partition_path, non_ab_partition_path)
		elif b_partition_path.is_file():
			move(b_partition_path, non_ab_partition_path)
