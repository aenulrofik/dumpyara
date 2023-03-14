#
# Copyright (C) 2022 Dumpyara Project
#
# SPDX-License-Identifier: GPL-3.0
#

from pathlib import Path
from sebaubuntu_libs.liblogging import LOGI
from sebaubuntu_libs.libreorder import strcoll_files_key

from dumpyara.utils.files import get_recursive_files_list, rmtree_recursive
from dumpyara.steps.step_1 import step_1
from dumpyara.steps.step_2 import step_2
from dumpyara.steps.step_3 import step_3

def dumpyara(file: Path, output_path: Path, debug: bool = False):
	"""Dump an Android firmware."""
	file = file
	output_path = output_path

	# Output folder
	path = output_path / file.stem

	# Temporary directories
	extracted_archive_path = path / "temp_extracted_archive"
	raw_images_path = path / "temp_raw_images"

	try:
		# Make output and temporary directories
		path.mkdir(parents=True)
		extracted_archive_path.mkdir()
		raw_images_path.mkdir()

		LOGI("Step 1 - Extracting archive")
		step_1(file, extracted_archive_path)

		LOGI("Step 2 - Preparing partition images")
		step_2(extracted_archive_path, raw_images_path)

		LOGI("Step 3 - Extracting partitions")
		step_3(raw_images_path, path)

		LOGI("Step 4 - Finalizing")
		# Update files list
		files_list = sorted(
			get_recursive_files_list(path, relative=True),
			key=strcoll_files_key
		)

		# Create all_files.txt
		LOGI("Creating all_files.txt")
		(path / "all_files.txt").write_text(
			"\n".join([str(file) for file in files_list]) + "\n"
		)

		return path
	finally:
		if not debug:
			# Remove temporary directories if they exist
			if extracted_archive_path.exists():
				rmtree_recursive(extracted_archive_path)

			if raw_images_path.exists():
				rmtree_recursive(raw_images_path)
