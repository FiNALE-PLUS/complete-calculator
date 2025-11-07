import binascii
import os
import struct
from datetime import datetime
from os.path import split

from pathlib import Path

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import simpledialog
from tkinter import messagebox
from typing import TypedDict

# Segments are 4000 hex long
SEGMENT_SIZE = int("40000", 16)


class CompleteFileContent(TypedDict):
    content_checksum: bytes
    head_checksum: bytes
    foot_checksum: bytes

    minor_version: bytes
    major_version: bytes

    year: bytes
    month: bytes
    day: bytes
    hour: bytes
    minute: bytes
    second: bytes


class ExtendCompleteDataParser:
    def __init__(self):
        self.content_checksum: bytes = bytes.fromhex("00000000")
        self.head_checksum: bytes = bytes.fromhex("00000000")
        self.foot_checksum: bytes = bytes.fromhex("00000000")

        # Default version is 1.00
        self.minor_version: bytes = bytes.fromhex("0000")
        self.major_version: bytes = bytes.fromhex("01")

        self.year: bytes = bytes.fromhex("0100")
        self.month: bytes = bytes.fromhex("01")
        self.day: bytes = bytes.fromhex("01")
        self.hour: bytes = bytes.fromhex("00")
        self.minute: bytes = bytes.fromhex("00")
        self.second: bytes = bytes.fromhex("00")

    @classmethod
    def get_version_string(cls, major_version: bytes, minor_version: bytes) -> str:
        return f"{struct.unpack('B', major_version)[0]}.{struct.unpack('H', minor_version)[0]}"

    def get_self_version_string(self) -> str:
        return self.get_version_string(self.major_version, self.minor_version)

    @classmethod
    def calculate_content_checksum(cls, complete_content: bytes) -> bytes:
        return bytes.fromhex(hex(binascii.crc32(complete_content))[2:])[::-1]

    def __bytes__(self) -> bytes:
        """
        Generates the byte content of the complete file that would represent the contents of this object's fields.
        Forcibly regenerates ``content_checksum`` for the object,
        preventing the output from having an incorrect checksum when returned.
        :return: The content of a complete file containing the fields of this object.
        """
        content = self.__get_complete_content_bytes()
        self.content_checksum = self.calculate_content_checksum(content)

        return self.content_checksum + content

    def save(self, output_path: Path) -> None:
        """
        Writes the contents of the class to ``output_path``, as a `.complete` file.

        :param output_path: The ``Path`` to write the file to.
        """
        file_content = self.__bytes__()

        with open(output_path, "wb") as content_file:
            content_file.write(file_content)

    def __get_complete_content_bytes(self) -> bytes:
        """
        Encoded contents of the object, without the final checksum prepended to the beginning of the byte sequence.
        Users looking to obtain a `.complete` file byte sequence should use ``__bytes__`` instead.

        :return: A byte sequence representing the encoded contents of this object's fields, bar ``content_checksum``.
        """
        return (self.head_checksum + self.foot_checksum + self.minor_version + self.major_version + bytes.fromhex(
            "00") +
                self.year + self.month + self.day + self.hour + self.minute + self.second + bytes.fromhex("00") * 9)

    def generate_values_using_extend_file(self, extend_path: Path, version: str, timestamp: datetime) -> None:
        """
        Generates a complete file using an extend file (``extend_path``) for its checksums,
        and ``version``/``timestamp`` for necessary metadata.

        :param extend_path: The ``Path`` of the extend file to generate checksums for.
        :param version: The version of the game this complete file is intended to be targeting.
        :param timestamp: The timestamp to add to the complete file. **Cannot** be arbitrary, as having this different
        to other files within the image will cause the extend file to not be loaded.
        """

        version_parts = version.split(".")

        # Validate version string
        if len(version_parts) != 2:
            raise ValueError("Version string format should be {uint8}.{uint16}")
        try:
            major_version = int(version_parts[0])
            minor_version = int(version_parts[1])
        except:
            raise ValueError(
                "Version string does not contain integers in its components (Version string format should be {uint8}.{uint16})")
        # Check value fits in allocated space
        if major_version < 0 or major_version > 255:
            raise ValueError(f"Major version must be between 0 and 255 (got {major_version} from {version})")
        if minor_version < 0 or minor_version > 65535:
            raise ValueError(f"Major version must be between 0 to 65535 (got {minor_version} from {version})")

        # Generate checksums from extend file
        self.load_extend_file_checksums(extend_path)

        self.minor_version = struct.pack('H', minor_version)
        self.major_version = struct.pack('B', major_version)

        self.year = struct.pack('H', timestamp.year)
        self.month = struct.pack('B', timestamp.month)
        self.day = struct.pack('B', timestamp.day)
        self.hour = struct.pack('B', timestamp.hour)
        self.minute = struct.pack('B', timestamp.minute)
        self.second = struct.pack('B', timestamp.second)

        self.content_checksum = bytes.fromhex(hex(binascii.crc32(self.__get_complete_content_bytes()))[2:])[::-1]

    def load_extend_file_checksums(self, input_path: Path) -> None:
        with open(input_path, "rb") as f:
            # Calculate file head sum
            self.head_checksum = bytes.fromhex(hex(binascii.crc32(f.read(SEGMENT_SIZE)))[2:])[::-1]

            # Calculate file foot sum
            f.seek(os.path.getsize(input_path) - SEGMENT_SIZE)
            self.foot_checksum = bytes.fromhex(hex(binascii.crc32(f.read(SEGMENT_SIZE)))[2:])[::-1]

    @classmethod
    def get_values_from_complete_file(cls, input_path: Path) -> CompleteFileContent:
        """
        Reads the necessary values from the complete file at ``input_path``, and returns them as a ``CompleteFileContent``.

        :param input_path: The ``Path`` of the complete file to parse.
        """
        with open(input_path, "rb") as f:
            content_checksum = f.read(4)
            head_checksum = f.read(4)
            foot_checksum = f.read(4)

            # Read uint16 for minor version
            minor_version = f.read(2)
            # Read uint8 for major version
            major_version = f.read(1)
            # Move offset by one to next data
            f.read(1)

            year = f.read(2)
            month = f.read(1)
            day = f.read(1)
            hour = f.read(1)
            minute = f.read(1)
            second = f.read(1)

        data = CompleteFileContent(
            content_checksum=content_checksum,
            head_checksum=head_checksum,
            foot_checksum=foot_checksum,

            minor_version=minor_version,
            major_version=major_version,

            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
        )

        return data

    @classmethod
    def parse_complete_date(cls, year: bytes, month: bytes, day: bytes, hour: bytes, minute: bytes, second: bytes) -> datetime:
        return datetime(
            year=struct.unpack('H', year)[0],
            month=struct.unpack('B', month)[0],
            day=struct.unpack('B', day)[0],
            hour=struct.unpack('B', hour)[0],
            minute=struct.unpack('B', minute)[0],
            second=struct.unpack('B', second)[0]
        )

    @classmethod
    def parse_date_and_version_from_complete_file(cls, input_path: Path) -> (datetime, str):
        data = cls.get_values_from_complete_file(input_path)

        parsed_date = cls.parse_complete_date(data["year"], data["month"], data["day"], data["hour"], data["minute"], data["second"])
        version = cls.get_version_string(data["major_version"], data["minor_version"])

        return parsed_date, version

    def load_complete_file(self, input_path: Path) -> None:
        """
        Parses all values from a .extend2.complete file.

        :param input_path: The path of the file to parse.
        :return: None
        """

        data = self.get_values_from_complete_file(input_path)

        self.content_checksum = data["content_checksum"]
        self.head_checksum = data["head_checksum"]
        self.foot_checksum = data["foot_checksum"]

        self.minor_version = data["minor_version"]
        self.major_version = data["major_version"]

        self.year = data["year"]
        self.month = data["month"]
        self.day = data["day"]
        self.hour = data["hour"]
        self.minute = data["minute"]
        self.second = data["second"]

    def __str__(self):

        file_timestamp = datetime(
            year=struct.unpack('H', self.year)[0],
            month=struct.unpack('B', self.month)[0],
            day=struct.unpack('B', self.day)[0],
            hour=struct.unpack('B', self.hour)[0],
            minute=struct.unpack('B', self.minute)[0],
            second=struct.unpack('B', self.second)[0]
        )

        return (
            f"Content checksum: {self.content_checksum.hex()}\n"
            f"Head checksum: {self.head_checksum.hex()}\n"
            f"Foot checksum: {self.foot_checksum.hex()}\n"
            f"Version: {self.get_self_version_string()}\n"
            f"Timestamp: {file_timestamp}"
        )


class ExtendCompleteWindowManager(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        # Frame manager from: https://www.digitalocean.com/community/tutorials/tkinter-working-with-classes

        # Adding a title to the window
        self.wm_title("Maimai Extend Toolkit")

        # creating a frame and assigning it to container
        container = tk.Frame(self)
        # specifying the region where the frame is packed in root
        container.grid()

        # configuring the location of the container using grid
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # We will now create a dictionary of frames
        self.frames = {}
        # we'll create the frames themselves later but let's add the components to the dictionary.
        for F in (MainPage,):
            frame = F(container, self)

            # the windows class acts as the root window for the frames.
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Using a method to switch frames
        self.resizable(width=False, height=False)
        self.show_frame(MainPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        # raises the current frame to the top
        frame.tkraise()


class MainPage(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        self.data_manager = ExtendCompleteDataParser()

        label = tk.Label(self, text="Data Configuration", pady=5)
        label.grid(row=0, column=0, sticky="nsew", columnspan=3)

        input_extend_label = ttk.Label(self, text="Input Extend File: ")
        input_extend_label.grid(row=1, column=0, sticky="nsew")
        self.input_extend_file = tk.StringVar(self)
        input_extend_entry = ttk.Entry(self, textvariable=self.input_extend_file, state="readonly", width=50)
        input_extend_entry.grid(row=1, column=1, sticky="nsew")
        input_extend_dialog_button = ttk.Button(self, text="Select File...",
                                                command=lambda: self.select_input_extend_file())
        input_extend_dialog_button.grid(row=1, column=2, sticky="nsew")

        output_extend_label = ttk.Label(self, text="Output Extend File: ")
        output_extend_label.grid(row=2, column=0, sticky="nsew")
        self.output_extend_file = tk.StringVar(self)
        output_extend_entry = ttk.Entry(self, textvariable=self.output_extend_file, state="readonly")
        output_extend_entry.grid(row=2, column=1, sticky="nsew")
        output_extend_dialog_button = ttk.Button(self, text="Select File...",
                                                 command=lambda: self.select_output_extend_file())
        output_extend_dialog_button.grid(row=2, column=2, sticky="nsew")

        self.major_version = tk.IntVar(self)
        self.major_version.set(1)
        self.minor_version = tk.IntVar(self)
        self.minor_version.set(97)
        version_row_label = ttk.Label(self, text="Game Version: ")
        version_row_label.grid(row=3, column=0, sticky="nsew")
        version_input_frame = tk.Frame(self)
        version_input_frame.grid(row=3, column=1, columnspan=2, sticky="nsew")
        major_version_input = ttk.Spinbox(version_input_frame, from_=1, to=255, textvariable=self.major_version)
        major_version_input.grid(row=0, column=0, sticky="nsew")
        separator_label = ttk.Label(version_input_frame, text=".")
        separator_label.grid(row=0, column=1, sticky="nsew")
        minor_version_input = ttk.Spinbox(version_input_frame, from_=1, to=65535, textvariable=self.minor_version)
        minor_version_input.grid(row=0, column=2, sticky="nsew")

        date_label = tk.Label(self, text="File Timestamp", anchor=tk.CENTER, pady=5)
        date_label.grid(row=4, column=0, sticky="nsew", columnspan=3)
        datetime_frame = tk.Frame(self)
        datetime_frame.grid(row=5, column=0, columnspan=3, sticky="nsew")

        self.year = tk.IntVar(self)
        year_label = ttk.Label(datetime_frame, text="Year", anchor=tk.CENTER)
        year_label.grid(row=0, column=0, sticky="nsew")
        year_input = ttk.Spinbox(datetime_frame, from_=1, to=9999, textvariable=self.year, width=10)
        year_input.grid(row=1, column=0, sticky="nsew")

        self.month = tk.IntVar(self)
        month_label = ttk.Label(datetime_frame, text="Month", anchor=tk.CENTER)
        month_label.grid(row=0, column=1, sticky="nsew")
        month_input = ttk.Spinbox(datetime_frame, from_=1, to=12, textvariable=self.month, width=11)
        month_input.grid(row=1, column=1, sticky="nsew")

        self.day = tk.IntVar(self)
        day_label = ttk.Label(datetime_frame, text="Day", anchor=tk.CENTER)
        day_label.grid(row=0, column=2, sticky="nsew")
        day_input = ttk.Spinbox(datetime_frame, from_=1, to=31, textvariable=self.day, width=11)
        day_input.grid(row=1, column=2, sticky="nsew")

        self.hour = tk.IntVar(self)
        hour_label = ttk.Label(datetime_frame, text="Hour", anchor=tk.CENTER)
        hour_label.grid(row=0, column=3, sticky="nsew")
        hour_input = ttk.Spinbox(datetime_frame, from_=0, to=23, textvariable=self.hour, width=11)
        hour_input.grid(row=1, column=3, sticky="nsew")

        self.minute = tk.IntVar(self)
        minute_label = ttk.Label(datetime_frame, text="Minute", anchor=tk.CENTER)
        minute_label.grid(row=0, column=4, sticky="nsew")
        minute_input = ttk.Spinbox(datetime_frame, from_=0, to=59, textvariable=self.minute, width=11)
        minute_input.grid(row=1, column=4, sticky="nsew")

        self.second = tk.IntVar(self)
        second_label = ttk.Label(datetime_frame, text="Second", anchor=tk.CENTER)
        second_label.grid(row=0, column=5, sticky="nsew")
        second_input = ttk.Spinbox(datetime_frame, from_=0, to=59, textvariable=self.second, width=11)
        second_input.grid(row=1, column=5, sticky="nsew")

        cur_date = datetime.now()

        self.year.set(cur_date.year)
        self.month.set(cur_date.month)
        self.day.set(cur_date.day)
        self.hour.set(cur_date.hour)
        self.minute.set(cur_date.minute)
        self.second.set(cur_date.second)

        load_complete_vals_button = ttk.Button(self, text="Load date and game version from existing complete file...", padding=5,
                                               command=lambda: self.get_date_and_version_from_complete_file())
        load_complete_vals_button.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

        generate_button = ttk.Button(self, text="Generate complete file", padding=5,
                                     command=lambda: self.generate_complete_file())
        generate_button.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

    def get_date_and_version_from_complete_file(self):
        try:
            complete_path = filedialog.askopenfilename(
                filetypes=(("Complete Files", "*.extend.complete *.extend2.complete"), ("All files", "*")))

            parsed_date, parsed_version = ExtendCompleteDataParser.parse_date_and_version_from_complete_file(Path(complete_path))

            split_version = parsed_version.split(".")

            self.major_version.set(split_version[0])
            self.minor_version.set(split_version[1])

            self.year.set(parsed_date.year)
            self.month.set(parsed_date.month)
            self.day.set(parsed_date.day)

            self.hour.set(parsed_date.hour)
            self.minute.set(parsed_date.minute)
            self.second.set(parsed_date.second)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during complete value parsing: {e}")

    def select_input_extend_file(self):
        self.input_extend_file.set(
            filedialog.askopenfilename(filetypes=(("Extend Files", "*.extend *.extend2"), ("All files", "*"))))

    def select_output_extend_file(self):
        save_path = filedialog.asksaveasfilename(
            filetypes=(("Complete Files", "*.extend.complete *.extend2.complete"), ("All files", "*")))
        file_name = os.path.basename(save_path)
        if len(file_name.split(".")) == 1:
            save_path += ".extend2.complete"

        self.output_extend_file.set(save_path)

    def generate_complete_file(self):
        try:
            self.data_manager.generate_values_using_extend_file(
                Path(self.input_extend_file.get()),
                f"{self.major_version.get()}.{self.minor_version.get()}",
                datetime(self.year.get(), self.month.get(), self.day.get(), self.hour.get(), self.minute.get(),
                         self.second.get()))

            self.data_manager.save(Path(self.output_extend_file.get()))

            messagebox.showinfo("Success", "File generated successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during file generation: {e}")


if __name__ == "__main__":
    manager = ExtendCompleteWindowManager()
    manager.mainloop()
