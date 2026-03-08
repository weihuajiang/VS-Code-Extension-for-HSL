# Auto load commands

In rack loading commands, which yield data, the relevant data \(barcodes, presence of containers, etc\) are direct\-ly appended to the command acknowledgement, as long as no errors have occurred\.

- 
	- 
		1. Initialization

__Command: __\(2 caps\.\)

__Parameter: __\(2 lower\-case letters and parameter value\)

Parameter\-range

Default

CP

__Description__

__II__



__\[SFCO\.0005\]__

id\#\#\#\#

0\.\.9999

0

1

__Initialize Auto load__

Identification number

__Ii__id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

__IV__



__\[SFCO\.0251\]__

id\#\#\#\#

0\.\.9999

0

1

__Move Auto load to Z save position__

Identification number

__IV__id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

- 
	- 
		1. Carrier handling

__Command: __\(2 caps\.\)

__Parameter: __\(2 lower\-case letters and parameter value\)

Parameter\-range

Default

CP

__Description__

__CI__

__\[SFCO\.0013\]__

id\#\#\#\# cp\#\# bi\#\#\#\# bw\#\#\# cv\#\#\#\#

0\.\.9999

1\.\.54

0\.\.4700

1\.\.999

15\.\.1600

0

1

43

85

1281

1

__Identify carrier \(determine carrier type\)__

Identification number

Carrier position \(slot number\) Carrier ID barcode position \[0\.1 mm\]

Carrier ID barcode reading window width \[0\.1mm\]

Carrier reading speed \[0\.1 mm\]/s



__CI __id\#\#\#\#

er\#\#/\#\# bb/nn'\.\.\.'\.

0\.\.9999

Identification number

Error message	\(see "er" definition\)

Barcode identification

nn = number of digits in the single barcode data

CIid1234er00/00bb/0812345678

__CT__

__\[SFCO\.0075\]__

id\#\#\#\# cp\#\#

0\.\.9999

1\.\.54

0

1

1

__Check presence of single carrier__

Identification number

Carrier position \(slot number\)



__CT __id\#\#\#\#

er\#\#/\#\# ct\#

0\.\.9999

0\.\.1

Identification number

Error message	\(see "er" definition\) Presence or absence

__ct0	Rack not present__

__ct1	Rack present__

__CA__



__\[SFCO\.0015\]__

id\#\#\#\#

0\.\.9999

0

1

__Push out carrier to loading tray \(after identification CI\) __Identification number

__CA __id\#\#\#\#er\#\#/\#\#

\(see "er" definition\)

__CR__

__\[SFCO\.0016\]__

id\#\#\#\# cp\#\#

0\.\.9999

1\.\.54

0

1

1

__Unload carrier__

Identification number

Carrier position \(slot number\)



__CR __id\#\#\#\#er\#\#/\#\#

\(see "er" definition\)

__Command: __\(2 caps\.\)

__Parameter: __\(2 lower\-case letters and parameter value\) 1\) only relevant for 2D Autoload / 2\) only relevant for 1D Autoload

Parameter\-range

Default

CP

__Description__

__CL__



__\[SFCO\.0014\]__

id\#\#\#\# bd\# bp\#\#\#\# cn\#\# co\#\#\#\# cf\#\#\# ea\#

ma\#\#\#\# *\#\#\#\# \#\#\# \#\#\#\# *1\)

mr\# cv\#\#\#\#

0\.\.9999

0\.\.1

0\.\.4700

0\.\.32

0\.\.4700

1\.\.999

0\.\.1

0\.\.1000

0\.\.2500

0\.\.1000

0\.\.1500

0 \.\.1

15\.\.1600

0

0

100

32

150

100

0

0

0

0

0

0

1281

1

__Load carrier__

Identification number

Barcode reading direction \(0 = vertical 1 = horizontal\) Barcode reading positions of first barcode \[0\.1mm\] Number of containers \(cups, plates\) in a carrier Distance between containers \(pattern\) \[0\.1 mm\] Width of reading window \[0\.1 mm\]

Carrier read mode

0 = fix grid

1 = free definable grid \(see commands DB & DR\) Region of Interest \(ROI\): YR0, ZR, YR, ZR \[0\.1mm\]

1. value: YR0 \(Y\-origin, typically a negative value\)
2. value: ZR \(Z\-origin as Z coordinate\)

\. value: YR \(Window width; 0000 = ROI not relevant\)

\. value: ZR \(Window height; 0000 = ROI not relevant\) All values in \[0\.1mm\], definitions *see *Fig\. 7

If YR = 0000 :

Standard values are set according parameter „bd“

ROI YR0 \(Y\-origin\) direction 0=positive	1=negative Carrier reading speed \[0\.1 mm\]/s

__CL __id\#\#\#\#

er\#\#/\#\#

__vl__nnnn nnnn \.\.

nnnn nnnn 1\)

ci\*\*\*\*\*\*\*\*

bb/nn'\.\.\.'/nn'\.\.\.'/nn'\.\.\.'\.

\.

0\.\.9999

0\.\.FFFFFFFF

Identification number

Error message	\(see "er" definition\)

Container code length, information separated by blank \(' '\) nnnn = number of digits of code length

Container presence or absence \(1 = present\)

MSB	LSB

Bit 31 \(MSB\) = Cup 32	Bit 0 \(LSB\) = Cup 1

Container barcode – information separated by slashes \('/'\)\. nn = number of digits in barcode

\(Number of barcode digits __*bb/nn *__is limited to 99\. If the barcode length is higher than 99 characters, this value is set to 00 and the real length have to be taken out of parameter __*vl*__\)

Too long codes can be requested with command “VKvn\#\#” 1\)

__Example:__

CLid3334er00/00ciFFFFFFFFvl0008 0007 0004 0011 0000

__0255__… bb/08HIV12345/07HBS1234567/04T123/11A345386/00/__00__/…

In case of faulty reading \(no read, plausibility conflicts,

etc\.\) both length parameter are set to 0\.

Bit 31

Bit 30

Bit 29

Bit 28

Bit 27

Bit 4

Bit 3

Bit 2

Bit 1

Bit 0

Bit 54

Bit 53

Bit 52

Bit 51

Bit 50

Bit 4

Bit 3

Bit 2

Bit 1

Bit 0

Bit 54

Bit 53

Bit 52

Bit 51

Bit 50

Bit 4

Bit 3

Bit 2

Bit 1

Bit 0

__Command: __\(2 caps\.\)

__Parameter: __\(2 lower\-case letters and parameter value\)

Parameter\-range

Default

CP

__Description__

__CP__



__\[SFCO\.0017\]__

id\#\#\#\# cl\*\*\*\*\*\*\*\*\*\*\*\*\*\*

cb\*\*\*\*\*\*\*\*\*\*\*\*\*\*

0\.\.9999

0\.\.7FFFFFFF FFFFFF 0\.\.7FFFFFFF FFFFFF

0

0

1

__Set loading indicators \(LED's\)__

Identification number Bit pattern of LED‘s 1 = on 0 = off

Blink pattern of LED‘s 1 = blinking 0 = steady

__MSB	LSB__

Bit 54 \(MSB\) = Position 55	Bit 0 \(LSB\) = Position 1

__CP __id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

__CS__



__\[SFCO\.0018\]__

id\#\#\#\#

0\.\.9999

0

1

__Check for presence of carriers on loading tray__

Identification number

__CS __id\#\#\#\#

er\#\#/\#\# cd\*\*\*\*\*\*\*\*\*\*\*\*\*\*

0\.\.9999

0\.\.7FFFFFFF FFFFFF

Identification number

Error message	\(see "er" definition\)

Bit pattern of carrier positions \( entry positions\) 1 = present

__MSB	LSB__

Bit 54 \(MSB\) = Position 55	Bit 0 \(LSB\) = Position 1

__Command: __\(2 caps\.\)

__Parameter: __\(2 lower\-case letters and parameter value\) 1\) only relevant for 2D Autoload / 2\) only relevant for 1D Autoload

Parameter\-range

Default

CP

__Description__

__CB__



__\[SFCO\.0072\]__

id\#\#\#\# bt\*\*

mq\*\* 1\)

mb\#\# 1\)

mo\#\#\# *\(7\) *1\)

0\.\.9999

00\.\.FF

00\.\.FF

1…10

0\.\.999

0

7F

00

1

000

1

__Set barcode types and 2D reader features__

Identification number

__Barcode types__: \(1D code types\)

__MSB	LSB__

1st character	2nd character

Bit 0 = ISBT Standard	Bit 4 = Code 2of 5 Interleaved Bit 1 = Code 128 \(Subset B and C\) Bit 5 = UPC A/E

Bit 2 = Code 39	Bit 6 = YESN/EAN 8

Bit 3 = Codabar	Bit 7 = Code 93

__Additional code types :__2D \(and stacked\) code types

__MSB	LSB__

1st character	2nd character

Bit 0 : Data Matrix	Bit 4 : PDF 417

Bit 1 : QR Code	Bit 5 : Micro PDF 417

Bit 2 : Maxi Code	Bit 6 : GS1 DataBar

Bit 3 : Aztec	Bit 7 : EAN/UCC Comp

Number of maximum codes per image \(ROI\) Illumination settings

1\. to 4\. values: Internal illumination

1. value: external illumination ON
2. value: gain \(0 \.\. 15\)
3. value: exposure time \( 50 …500 us\)

All values = 0: automatic selection of illumination

__CB __id\#\#\#\#

er\#\#/\#\#

0\.\.9999

Identification number

error message	\(see "er" definition\)

__DB__



id\#\#\#\# vn\#\# bp\#\#\#\#

ma\#\#\#\# *\#\#\#\# \#\#\# \#\#\#\# *1\)

mr\#

0\.\.9999

0\.\.32

0\.\.4700

0\.\.1000

0\.\.2500

0\.\.1000

0\.\.1500

0 \.\. 1

0

1

100

0

0

0

0

0

1

__Set code reading features for free definable carrier__

Identification number

Labware position number \(= code index\) Code reading position \[0\.1mm\]

Region of Interest \(ROI\): YR0, ZR, YR, ZR \[0\.1mm\]

1. value: YR0 \(Y\-origin, typically a negative value\)
2. value: ZR \(Z\-origin as Z coordinate\)

\. value: YR \(Window width; 0000 = ROI not relevant\)

\. value: ZR \(Window height; 0000 = ROI not relevant\) All values in \[0\.1mm\], definitions *see *Fig\. 7

ROI YR0 \(Y\-origin\) direction 0=positive	1=negative

__DB __id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

__DR__



id\#\#\#\#

0\.\.9999

0

1

__Reset free definable carrier settings__

Identification number

__DR __id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

__CW__



__\[SFCO\.0140\]__

id\#\#\#\# cp\#\#

0\.\.9999

1. \.54

0

1

1

__Unload carrier finally__

Identification number

Carrier position \(slot number\)

__CW __id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

Bit 7

Bit 6

Bit 5

Bit 4

Bit 3

Bit 2

Bit 1

Bit 0

Bit 7

Bit 6

Bit 5

Bit 4

Bit 3

Bit 2

Bit 1

Bit 0

__Command: __\(2 caps\.\)

__Parameter: __\(2 lower\-case letters and parameter value\) 1\) only relevant for 2D Autoload / 2\) only relevant for 1D Autoload

Parameter\-range

Default

CP

__Description__

__CU__



__\[SFCO\.0146\]__

id\#\#\#\# cu\#

0\.\.9999

0\.\.1

0

0

1

__Set carrier monitoring__

Identification number

0 = monitoring off 1 = monitoring on

__CU __id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

__CN__



__\[SFCO\.0238\]__

id\#\#\#\# cp\#\#

0\.\.9999

1\.\.54

0

1

1

__Take out the carrier to identification position__

Identification number

Carrier position \(slot number\)

__CN __id\#\#\#\#er\#\#/\#\#	\(see "er" definition\)

- 
	- 
		1. Auto load query

Bit n

Bit n\-1

Bit n\-2

Bit n\-3

Bit n\-4

Bit 4

Bit 3

Bit 2

Bit 1

Bit 0

__Query: __\(2 caps\.\) 1\) only relevant for 2D Autoload

__Parameter: __\(2 lower\-case letters and parameter value\)

Parameter\-range

Def\.

__Description__

__RC__



__\[SFCO\.0045\]__

id\#\#\#\#

0\.\.9999

0

__Query Presence of carrier on deck__

__RC __id\#\#\#\#

er\#\#/\#\# cd\*\*\*\*\*\*\*\*\*\*\*\*\*

\* ce\*\*…\.\(26\)

0\.\.9999

0\.\.99/0\.\.99

0\.\.7FFFF…

0\.\.7FFFF…

Identification number

Error code / Trace information \(see "er" definition\)

*old Bit pattern of carrier positions \(14 characters for compatibility only\) *Bit pattern of extended carrier positions \(26 characters\) = 104 \(slots\) \(contains all possible 104 slot bits\)

1 = presence

__MSB	LSB__

Bit n = \(MSB\) = Position n	Bit 0 \(LSB\) = Position 1

__QA__



__\[SFCO\.0200\]__

id\#\#\#\#

0\.\.9999

0

__Request auto load slot position__

QAid\#\#\#\#

er\#\#/\#\# qa\#\#

0\.\.9999

0\.\.99/0\.\.99

0\.\.54

Identification number

Error code / Trace information \(see "er" definition\) Slot position

__CQ__



__\[SFCO\.0341\]__

id\#\#\#\#

0\.\.9999

0

__Request auto load module type__

CQid\#\#\#\#

er\#\#/\#\# cq\#

0\.\.9999

0\.\.99/0\.\.99

0\.\.9

Identification number

Error code / Trace information \(see "er" definition\) Auto load module type

0 = ML\-Star with 1D Code Scanner	1 = XRP Lite

2 = ML\-STAR with 2D Code Reader	3 \.\. 9 = reserve

VK 1\)



id\#\#\#\# vn\#\#

0\.\.9999

0 \.\.32

0

1

Request code data of an individual labware position

Labware position number

VKid\#\#\#\#

er\#\#/\#\# vn\#\# vm\#\# __vl__nnn 1\) vk…\.\.

0\.\.9999

0\.\.99/0\.\.99

0 \.\.32

1 \.\.32

1

1

Identification number

Error code / Trace information \(see "er" definition\) Requested labware position number

Number of readed barcodes Labware code length

Code information

__Example:__

VKid3334er00__vl008vk__HIV12345

Unread code or longer than 255 characters is given with length 00\. VKid3334er00__vl000vk__

__VL__1\)



id\#\#\#\#

0\.\.9999

0

__Request code data length of all read labware position of cmd “CL”__

VLid\#\#\#\#

er\#\#/\#\#

__vl__nnn nnn \.\.\.

…nnn nnn

0\.\.9999

0\.\.99/0\.\.99

Identification number

Error code / Trace information \(see "er" definition\) Container code length, information separated by blank \(' '\) nnn = number of digits of code length

__Example: __VLid3334er00/00vl008 007 004 011 000 __255__…

Unread or too long codes \(> 255 characters\) are given with length 000

