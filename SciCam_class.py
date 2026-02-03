from SciCamErrorDefine_const import *
from SciCamPayload_header import *
from SciCamInfo_header import *

class SciCamera():
	## @ingroup module_Other
	#  @~chinese
	#  @brief 初始化
	#  @param NULL
	#  @retval NULL
	#  @remarks 接口初始化
	#  @~english
	#  @brief Initialize
	#  @param NULL
	#  @retval NULL
	#  @remarks Initialize the interface
	def __init__(self):
		self._handle = ctypes.c_void_p()
		self.handle = pointer(self._handle)

	## @~chinese
	#  @brief 原始数据回调函数类型定义
	#  @details 用于注册图像数据或轮廓数据的回调函数
	#  @param payload [IN] 采集到的payload数据，可以是图像数据或轮廓数据
	#  @param tag [IN] 用户自定义参数，用于传递用户数据
	#  @retval NULL
	#  @remarks 该函数类型用于SciCam_RegisterPayloadCallBack接口
	#  @~english
	#  @brief Raw data callback function type definition
	#  @details Used to register callback functions for image data or contour data
	#  @param payload [IN] Acquired payload data, can be image data or contour data
	#  @param tag [IN] User-defined parameter for passing user data
	#  @retval NULL
	#  @remarks This function type is used for SciCam_RegisterPayloadCallBack interface
	fnOnPayload = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)

	## @ingroup module_SDKVersionInfo
	#  @~chinese
	#  @brief 获取SDK版本号
	#  @param NULL
	#  @retval 返回4字节版本号:
	#  | 主版本 | 次版本 | 修正版本 | 测试版本 |
	#  | --- | --- | --- | --- |
	#  | 8bits | 8bits | 8bits | 8bits |
	#  @remarks 例如返回值为0x01000001，即SDK版本号为V1.0.0.1
	#  @~english
	#  @brief Get SDK Version
	#  @param NULL
	#  @retval Always return 4 Bytes of version number:
	#  | Main | Sub | Rev | Test |
	#  | --- | --- | --- | --- |
	#  | 8bits | 8bits | 8bits | 8bits |
	#  @remarks For example, if the return value is 0x01000001, the SDK version is V1.0.0.1
	@staticmethod
	def SciCam_GetSDKVersion():
		SciCamCtrlDll.SciCam_GetSDKVersion.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetSDKVersion()
	
	## @ingroup module_Other
	#  @~chinese
	#  @brief 设置SDK日志输出路径
	#  @param logPath [IN] 文件夹路径(绝对路径)
	#  @retval 成功：@ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见：@ref SciCamErrorDefine_const "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Set the SDK log output path
	#  @param logPath [IN] Folder path (absolute path)
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine_const "Error Code List"
	#  @remarks NULL
	@staticmethod
	def SciCam_SetSDKLogPath(logPath):
		SciCamCtrlDll.SciCam_SetSDKLogPath.argtypes = ctypes.c_void_p
		SciCamCtrlDll.SciCam_SetSDKLogPath.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetSDKLogPath(logPath.encode('ascii'))

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 搜索设备
	#  @param devInfos [OUT] 搜索到的设备列表，详情参考：@ref PSCI_DEVICE_INFO_LIST "PSCI_DEVICE_INFO_LIST"
	#  @param tlType [IN] 传输层类型组合（0：搜索全部，其他如SciCam_TLType_Gige | SciCam_TLType_Usb3 仅搜索GigE和USB3.0设备）
	#  @retval 成功：@ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见：@ref SciCamErrorDefine_const "状态码"
	#  @remarks 当tlType为SciCam_TLType_CL_CAM_ONLY时，仅搜索CL采集卡下的相机。SciCam_TLType_CL_CAM_ONLY不能与其他tlType进行或操作
	#  @~english
	#  @brief Search for devices
	#  @param devInfos [OUT] List of discovered devices, references: @ref PSCI_DEVICE_INFO_LIST "PSCI_DEVICE_INFO_LIST"
	#  @param tlType [IN] Combination of transport layer types (0: search all, others like SciCam_TLType_Gige | SciCam_TLType_Usb3 only search for GigE and USB3.0 devices)
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine_const "Error Code List"
	#  @remarks When tlType is set to SciCam_TLType_CL_CAM_ONLY, it only searches for cameras under CL capture cards. SciCam_TLType_CL_CAM_ONLY cannot be combined with other tlType values using bitwise OR operations.
	@staticmethod
	def SciCam_DiscoveryDevices(devInfos, tlType):
		SciCamCtrlDll.SciCam_DiscoveryDevices.argtypes = (PSCI_DEVICE_INFO_LIST, ctypes.c_uint)
		SciCamCtrlDll.SciCam_DiscoveryDevices.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_DiscoveryDevices(ctypes.byref(devInfos), ctypes.c_uint(tlType))

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 创建相机句柄
	#  @param devInfo [IN] 设备信息结构体，详情参考：@ref PSCI_DEVICE_INFO "PSCI_DEVICE_INFO"
	#  @retval 成功：@ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见：@ref SciCamErrorDefine_const "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Create Device Handle
	#  @param devInfo [IN] Device Information Structure, references: @ref PSCI_DEVICE_INFO "PSCI_DEVICE_INFO"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine_const "Error Code List"
	#  @remarks NULL
	def SciCam_CreateDevice(self, devInfo):
		SciCamCtrlDll.SciCam_CreateDevice.argtypes = (ctypes.c_void_p, PSCI_DEVICE_INFO)
		SciCamCtrlDll.SciCam_CreateDevice.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_CreateDevice(ctypes.byref(self.handle), devInfo)

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 销毁设备句柄
	#  @retval 成功：@ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见：@ref SciCamErrorDefine_const "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Destroy Device Handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine_const "Error Code List"
	#  @remarks NULL
	def SciCam_DeleteDevice(self):
		SciCamCtrlDll.SciCam_DeleteDevice.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_DeleteDevice.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_DeleteDevice(self.handle)

	## @ingroup module_Other
	#  @~chinese
	#  @brief 注册设备监听事件
	#  @param hDev		[IN] 设备句柄
	#  @param fn		[IN] 回调函数指针
	#  @param tag		[IN] 用户自定义参数
	#  @retval NULL
	#  @remarks 通过注册回调方式，可实时获取到相机上线、离线等通知消息
	#  @~english
	#  @brief Registering device monitoring events
	#  @param payload	[IN] Device event
	#  @param fn		[IN] Callback function pointer
	#  @param tag		[IN] User-defined parameters
	#  @retval NULL
	#  @remarks By registering a callback, you can receive real-time notification messages such as camera online/offline events.
	def SciCam_RegisterEventCallback(self, CallBackFun, tag):
		SciCamCtrlDll.SciCam_RegisterEventCallback.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_RegisterEventCallback.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_RegisterEventCallback(self.handle, CallBackFun, tag)

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 打开设备
	#  @param hDev	[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 对于GigE和U3V设备为打开相机，CL设备为打开采集卡，可参考SciCam_CL_OpenCam
	#  @~english
	#  @brief Open Device
	#  @param hDev	[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks For opening cameras with GigE and U3V devices, and for opening capture cards with CL devices, refer to SciCam_CL_OpenCam
	def SciCam_OpenDevice(self):
		SciCamCtrlDll.SciCam_OpenDevice.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_OpenDevice.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_OpenDevice(self.handle)

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 关闭设备
	#  @param hDev	[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 通过SciCam_OpenDevice连接设备后，可以通过该接口断开设备连接，释放资源。如果是CL设备，关闭采集卡时会把采集卡下的所有相机一起关闭
	#  @~english
	#  @brief Close Device
	#  @param hDev	[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting to the device through SciCam_OpenDevice, you can use this interface to disconnect the device and release resources. If it is a CL device, closing the capture card will also close all cameras under the capture card.
	def SciCam_CloseDevice(self):
		SciCamCtrlDll.SciCam_CloseDevice.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_CloseDevice.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_CloseDevice(self.handle)

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 判断设备是否已连接
	#  @param hDev	[IN]  设备句柄
	#  @retval true: 设备已连接；false：设备未连接
	#  @remarks 对于GigE和U3V设备为相机是否已连接，对于CL设备为采集卡是否已连接，可参考SciCam_CL_IsCamOpen
	#  @~english
	#  @brief Check if the device is connected
	#  @param hDev	[IN]  Device handle
	#  @retval true: Device connected; false: Device not connected
	#  @remarks To check if the camera is connected for GigE and U3V devices, and to check if the capture card is connected for CL devices, refer to SciCam_CL_IsCamOpen.
	def SciCam_IsDeviceOpen(self):
		SciCamCtrlDll.SciCam_IsDeviceOpen.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_IsDeviceOpen.restype = ctypes.c_bool
		return SciCamCtrlDll.SciCam_IsDeviceOpen(self.handle)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 注册原始数据（图像数据/轮廓数据）回调
	#  @param hDev		[IN]  设备句柄
	#  @param fn		[IN]  回调函数指针
	#  @param tag		[IN]  自定义参数
	#  @param autoFree	[IN]  回调执行完是否释放payload，true为释放，false为不释放（手动释放payload可参考：SciCam_FreePayload）
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 通过该接口可以设置图像数据或轮廓数据回调函数，在调用SciCam_CreateDevice之后即可使用。 \n
	#  		采集图像数据或轮廓数据有两种方式： \n
	#  		方式一：调用SciCam_RegisterPayloadCallBack设置回调函数，然后调用SciCam_StartGrabbing开始采集，采集的图像/轮廓数据在设置的回调函数中返回。 \n
	#  		方式二：调用SciCam_StartGrabbing开始采集，然后在应用层循环调用SciCam_Grab获取得到图像/轮廓数据。 \n
	#  		采用方式二获取payload数据时，应用层需根据帧率控制好调用该接口的频率。
	#  		获取到的payload数据可通过SciCamPayload.h中相应的接口获取到payload相关属性，转换成所需数据格式。
	#  @~english
	#  @brief Register callback for raw data (image data/contour data).
	#  @param hDev		[IN]  Device handle
	#  @param fn		[IN]  Callback function pointer
	#  @param tag		[IN]  user defined parameters
	#  @param autoFree	[IN]  Whether to release the payload after the callback execution, true for release, false for not release (manually releasing payload can refer to: SciCam_FreePayload).
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks This interface allows you to set a callback function for image data or contour data, and it can be used after calling SciCam_CreateDevice. \n
	#  		There are two methods for capturing image data or contour data: \n
	#  		Method 1: Call SciCam_RegisterPayloadCallBack to set the callback function, then call SciCam_StartGrabbing to start capturing. The captured image/contour data will be returned in the set callback function. \n
	#  		Method 2: Call SciCam_StartGrabbing to start capturing, then in the application layer, loop calls SciCam_Grab to obtain image/contour data. \n
	#  		When using Method 2 to obtain payload data, the application layer should control the frequency of calling this interface based on the frame rate. \n
	#  		The obtained payload data can be converted into the desired data format by using the corresponding interfaces in SciCamPayload.h to access payload-related attributes.
	def SciCam_RegisterPayloadCallBack(self, CallBackFun, tag, autoFree):
		SciCamCtrlDll.SciCam_RegisterPayloadCallBack.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
		SciCamCtrlDll.SciCam_RegisterPayloadCallBack.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_RegisterPayloadCallBack(self.handle, CallBackFun, tag, ctypes.c_bool(autoFree))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 获取当前设备采集策略
	#  @param hDev		[IN]  设备句柄
	#  @param pStrategy	[OUT] 获取到的采集策略，详细参考： @ref SciCamGrabStrategy "SciCamGrabStrategy"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get the current device acquisition strategy
	#  @param hDev		[IN]  Device handle
	#  @param pStrategy	[OUT] The obtained acquisition strategy, references: @ref SciCamGrabStrategy "SciCamGrabStrategy"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetGrabStrategy(self, pStrategy):
		SciCamCtrlDll.SciCam_GetGrabStrategy.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetGrabStrategy.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetGrabStrategy(self.handle, ctypes.byref(pStrategy))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 设置采集策略
	#  @param hDev			[IN] 设备句柄
	#  @param grabStrategy	[IN] 采集策略，详细参考： @ref SciCamGrabStrategy "SciCamGrabStrategy"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Set the acquisition strategy
	#  @param hDev			[IN] Device handle
	#  @param grabStrategy	[IN] Grab strategy, references: @ref SciCamGrabStrategy "SciCamGrabStrategy"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_SetGrabStrategy(self, grabStrategy):
		SciCamCtrlDll.SciCam_SetGrabStrategy.argtypes = (ctypes.c_void_p, ctypes.c_int)
		SciCamCtrlDll.SciCam_SetGrabStrategy.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetGrabStrategy(self.handle, ctypes.c_int(grabStrategy))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 获取当前设备采集一帧的等待超时时间
	#  @param hDev		[IN]  设备句柄
	#  @param pTimeout	[OUT] 获取到的等待超时时间（单位：ms）
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 采集时采用的是超时等待机制，如果在超时等待时间内未完成采集完整一帧或等待超过超时时间也没采集到一帧，则会返回错误码，请合理设置等待超时时间
	#  @~english
	#  @brief Get the current device timeout waiting time for capturing one frame
	#  @param hDev		[IN]  Device handle
	#  @param pTimeout	[OUT] The obtained timeout waiting time(unit: ms)
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks During capture, a timeout waiting mechanism is used. If capturing a complete frame is not completed within the timeout waiting time or if no frame is captured within the specified timeout, an error code will be returned. Please set the timeout waiting time appropriately.
	def SciCam_GetGrabTimeout(self, pTimeout):
		SciCamCtrlDll.SciCam_GetGrabTimeout.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetGrabTimeout.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetGrabTimeout(self.handle, ctypes.byref(pTimeout))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 设置当前设备采集一帧所需的等待超时时间
	#  @param hDev		[IN]  设备句柄
	#  @param timeout	[IN]  等待超时时间（单位：ms）
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 采集时采用的是超时等待机制，如果在超时等待时间内未完成采集完整一帧或等待超过超时时间也没采集到一帧，则会返回错误码，请合理设置等待超时时间
	#  @~english
	#  @brief Set the timeout waiting time required for capturing one frame for the current device.
	#  @param hDev		[IN]  Device handle
	#  @param timeout	[IN]  Timeout waiting time（unit：ms）
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks During capture, a timeout waiting mechanism is used. If capturing a complete frame is not completed within the timeout waiting time or if no frame is captured within the specified timeout, an error code will be returned. Please set the timeout waiting time appropriately.
	def SciCam_SetGrabTimeout(self, timeout):
		SciCamCtrlDll.SciCam_SetGrabTimeout.argtypes = (ctypes.c_void_p, ctypes.c_uint)
		SciCamCtrlDll.SciCam_SetGrabTimeout.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetGrabTimeout(self.handle, ctypes.c_uint(timeout))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 获取采集时缓存队列大小
	#  @param hDev			[IN]  设备句柄
	#  @param pBufferCount	[OUT] 获取到的缓存队列大小
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 缓存队列越大越消耗资源，但同时也能减少丢帧概率，请合理分配缓存队列大小
	#  @~english
	#  @brief Retrieve the size of the buffer queue during grabbing
	#  @param hDev			[IN]  Device handle
	#  @param pBufferCount	[OUT] The size of the obtained buffer queue
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks A larger buffer queue consumes more resources, but it can also reduce the probability of frame drops. Please allocate the buffer queue size judiciously.
	def SciCam_GetGrabBufferCount(self, pBufferCount):
		SciCamCtrlDll.SciCam_GetGrabBufferCount.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetGrabBufferCount.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetGrabBufferCount(self.handle, ctypes.byref(pBufferCount))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 设置采集时缓存队列大小
	#  @param hDev			[IN]  设备句柄
	#  @param pBufferCount	[IN]  缓存队列大小
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 缓存队列越大越消耗资源，但同时也能减少丢帧概率，请合理分配缓存队列大小。 \n
	#  			bufferCount为0时表示不设置，使用推荐缓存策略。
	#  @~english
	#  @brief Retrieve the size of the buffer queue during grabbing
	#  @param hDev			[IN]  Device handle
	#  @param pBufferCount	[IN]  Buffer queue size
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks A larger buffer queue consumes more resources, but it can also reduce the probability of frame drops. Please allocate the buffer queue size judiciously. \n
	#  			When bufferCount is set to 0, it indicates that no specific value is set, and the recommended caching strategy should be used.
	def SciCam_SetGrabBufferCount(self, bufferCount):
		SciCamCtrlDll.SciCam_SetGrabBufferCount.argtypes = (ctypes.c_void_p, ctypes.c_uint)
		SciCamCtrlDll.SciCam_SetGrabBufferCount.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetGrabBufferCount(self.handle, ctypes.c_uint(bufferCount))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 开始采集
	#  @param hDev	[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Start grabbing
	#  @param hDev	[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_StartGrabbing(self):
		SciCamCtrlDll.SciCam_StartGrabbing.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_StartGrabbing.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_StartGrabbing(self.handle)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 停止采集
	#  @param hDev	[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Stop grabbing
	#  @param hDev	[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_StopGrabbing(self):
		SciCamCtrlDll.SciCam_StopGrabbing.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_StopGrabbing.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_StopGrabbing(self.handle)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 采集一帧数据（图像数据/轮廓数据）
	#  @param hDev		[IN]  设备句柄
	#  @param ppayload	[OUT] 一帧的数据
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 调用SciCam_RegisterPayloadCallBack接口注册回调后与该接口不兼容，请二取其一使用。 \n
	#  		获取到的payload数据可通过SciCamPayload.h中相应的接口获取到payload相关属性，转换成所需数据格式。 \n
	#  		帧数据使用完后请调用SciCam_FreePayload进行释放，避免设备无法继续采集的情况。
	#  @~english
	#  @brief Grab one frame of data (image data/contour data)
	#  @param hDev		[IN]  Device handle
	#  @param ppayload	[OUT] One frame of data
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After registering a callback using the SciCam_RegisterPayloadCallBack interface, it is not compatible with this interface. Please choose one of them to use. \n
	#  		The obtained payload data can be converted into the desired data format by using the corresponding interfaces in SciCamPayload.h to access payload-related attributes. \n
	#  		After using the frame data, please call SciCam_FreePayload for release to avoid situations where the device cannot continue capturing.
	def SciCam_Grab(self, ppayload):
		SciCamCtrlDll.SciCam_Grab.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
		SciCamCtrlDll.SciCam_Grab.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_Grab(self.handle, ppayload)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 释放一帧数据（图像数据/轮廓数据）
	#  @param hDev		[IN]  设备句柄
	#  @param payload	[IN]  一帧的数据
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Release a frame of data (image data/contour data)
	#  @param hDev		[IN]  Device handle
	#  @param payload	[IN]  One frame of data
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_FreePayload(self, payload):
		SciCamCtrlDll.SciCam_FreePayload.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_FreePayload.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_FreePayload(self.handle, payload)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 清除缓存队列数据
	#  @param hDev		[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Clear the cache queue data
	#  @param hDev		[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_ClearPayloadBuffer(self):
		SciCamCtrlDll.SciCam_ClearPayloadBuffer.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_ClearPayloadBuffer.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_ClearPayloadBuffer(self.handle)

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Integer属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值，如获取宽度信息则为"Width"
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_INT "PSCI_NODE_VAL_INT"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取int类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IInteger”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来获取相机设备XML中“IInteger”类型节点值，CL和CXP设备请参考接口：SciCam_GetIntValueEx
	#  @~english
	#  @brief Get Integer value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value, for example, using "Width" to get width
	#  @param pVal		[OUT] Structure pointer of camera features, references: @ref PSCI_NODE_VAL_INT "PSCI_NODE_VAL_INT"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks You can call this API to get the value of camera node with integer type after connecting the device. For key value, refer to MvCameraNode. All the node values of "IInteger" in the list can be obtained via this API. Key corresponds to the Name column. \n
	#  		This interface is only used to retrieve the values of "IInteger" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_GetIntValueEx.
	def SciCam_GetIntValue(self, key, pVal):
		SciCamCtrlDll.SciCam_GetIntValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, PSCI_NODE_VAL_INT)
		SciCamCtrlDll.SciCam_GetIntValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetIntValue(self.handle, key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Integer型属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值，如获取宽度信息则为"Width"
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置int类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IInteger”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“IInteger”类型节点值，CL和CXP设备请参考接口：SciCam_SetIntValueEx
	#  @~english
	#  @brief Set Integer value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value, for example, using "Width" to set width
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks You can call this API to get the value of camera node with integer type after connecting the device. For key value, refer to MvCameraNode. All the node values of "IInteger" in the list can be obtained via this API. Key corresponds to the Name column. \n
	#  		This interface is only used to set the values of "IInteger" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetIntValueEx.
	def SciCam_SetIntValue(self, key, val):
		SciCamCtrlDll.SciCam_SetIntValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64)
		SciCamCtrlDll.SciCam_SetIntValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetIntValue(self.handle, key.encode('ascii'), ctypes.c_int64(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Float属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_FLOAT "PSCI_NODE_VAL_FLOAT"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取float类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IFloat”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。
	#  		此接口仅用来获取相机设备XML中“IFloat”类型节点值，CL和CXP设备请参考接口：SciCam_GetFloatValueEx
	#  @~english
	#  @brief Get Float value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value
	#  @param pVal		[OUT] Structure pointer of camera features
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified float node. For detailed key value see: MvCameraNode. The node values of IFloat can be obtained through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to retrieve the values of "IFloat" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_GetFloatValueEx.
	def SciCam_GetFloatValue(self, key, pVal):
		SciCamCtrlDll.SciCam_GetFloatValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, PSCI_NODE_VAL_FLOAT)
		SciCamCtrlDll.SciCam_GetFloatValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetFloatValue(self.handle, key.encode('ascii'), ctypes.byref(pVal))
		
	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置float型属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置float类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IFloat”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“IFloat”类型节点值，CL和CXP设备请参考接口：SciCam_SetFloatValueEx
	#  @~english
	#  @brief Set float value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified float node. For detailed key value see: MvCameraNode. The node values of IFloat can be set through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to set the values of "IFloat" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetFloatValueEx.
	def SciCam_SetFloatValue(self, key, val):
		SciCamCtrlDll.SciCam_SetFloatValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double)
		SciCamCtrlDll.SciCam_SetFloatValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetFloatValue(self.handle, key.encode('ascii'), ctypes.c_double(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Boolean属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值
	#  @param pVal		[OUT] 返回给调用者有关设备属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取bool类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IBoolean”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来获取相机设备XML中“IBoolean”类型节点值，CL和CXP设备请参考接口：SciCam_GetBoolValueEx
	#  @~english
	#  @brief Get Boolean value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value
	#  @param pVal		[OUT] Structure pointer of camera features
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified bool nodes. For value of key, see MvCameraNode. The node values of IBoolean can be obtained through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to retrieve the values of "IBoolean" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_GetBoolValueEx.
	def SciCam_GetBoolValue(self, key, pVal):
		SciCamCtrlDll.SciCam_GetBoolValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetBoolValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetBoolValue(self.handle, key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Boolean型属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置bool类型的指定节点的值。strKey取值可以参考XML节点参数类型列表，表格里面数据类型为“IBoolean”的节点值都可以通过该接口设置，strKey参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“IBoolean”类型节点值，CL和CXP设备请参考接口：SciCam_SetBoolValueEx
	#  @~english
	#  @brief Set Boolean value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified bool nodes. For value of key, see MvCameraNode. The node values of IBoolean can be set through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to set the values of "IBoolean" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetBoolValueEx.
	def SciCam_SetBoolValue(self, key, val):
		SciCamCtrlDll.SciCam_SetBoolValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
		SciCamCtrlDll.SciCam_SetBoolValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetBoolValue(self.handle, key.encode('ascii'), ctypes.c_bool(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取String属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_STRING "PSCI_NODE_VAL_STRING"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取string类型的指定节点的值。Key取值可以参考XML节点参数类型列表，表格里面数据类型为“IString”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来获取相机设备XML中“IString”类型节点值，CL和CXP设备请参考接口：SciCam_GetStringValueEx
	#  @~english
	#  @brief Get String value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value
	#  @param pVal		[OUT] Structure pointer of camera features, references: @ref PSCI_NODE_VAL_STRING "PSCI_NODE_VAL_STRING"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified string nodes. For value of key, see MvCameraNode. The node values of IString can be obtained through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to retrieve the values of "IString" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_GetStringValueEx.
	def SciCam_GetStringValue(self, key, pVal):
		SciCamCtrlDll.SciCam_GetStringValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, PSCI_NODE_VAL_STRING)
		SciCamCtrlDll.SciCam_GetStringValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetStringValue(self.handle, key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置String型属性值
	#  @param hDev		[IN] 设备句柄
	#  @param key		[IN] 属性键值
	#  @param val		[IN] 想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置string类型的指定节点的值。Key取值可以参考XML节点参数类型列表，表格里面数据类型为“IString”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“IString”类型节点值，CL和CXP设备请参考接口：SciCam_SetStringValueEx
	#  @~english
	#  @brief Set String value
	#  @param hDev		[IN] Device handle
	#  @param key		[IN] Key value
	#  @param val		[IN] Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified string nodes. For value of key, see MvCameraNode. The node values of IString can be set through this interface, key value corresponds to the Name column.
	#  		This interface is only used to set the values of "IString" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetStringValueEx.
	def SciCam_SetStringValue(self, key, val):
		SciCamCtrlDll.SciCam_SetStringValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_SetStringValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetStringValue(self.handle, key.encode('ascii'), val.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Enum属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值，如获取像素格式信息则为"PixelFormat"
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_ENUM "PSCI_NODE_VAL_ENUM"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取Enum类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IEnumeration”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来获取相机设备XML中“IEnumeration”类型节点值，CL和CXP设备请参考接口：SciCam_GetEnumValueEx
	#  @~english
	#  @brief Get Enum value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value, for example, using "PixelFormat" to get pixel format
	#  @param pVal		[OUT] Structure pointer of camera features
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified Enum nodes. For value of key, see MvCameraNode, The node values of IEnumeration can be obtained through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to retrieve the values of "IEnumeration" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_GetEnumValueEx.
	def SciCam_GetEnumValue(self, key, pVal):
		SciCamCtrlDll.SciCam_GetEnumValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, PSCI_NODE_VAL_ENUM)
		SciCamCtrlDll.SciCam_GetEnumValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetEnumValue(self.handle, key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Enum型属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值，如获取像素格式信息则为"PixelFormat"
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置Enum类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IEnumeration”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“IEnumeration”类型节点值，CL和CXP设备请参考接口：SciCam_SetEnumValueEx
	#  @~english
	#  @brief Set Enum value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value, for example, using "PixelFormat" to set pixel format
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified Enum nodes. For value of key, see MvCameraNode, The node values of IEnumeration can be obtained through this interface, key value corresponds to the Name column. \n
	#  		This interface is only used to set the values of "IEnumeration" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetEnumValueEx.
	def SciCam_SetEnumValue(self, key, val):
		SciCamCtrlDll.SciCam_SetEnumValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64)
		SciCamCtrlDll.SciCam_SetEnumValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetEnumValue(self.handle, key.encode('ascii'), ctypes.c_int64(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Enum型属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值，如获取像素格式信息则为"PixelFormat"
	#  @param val		[IN]  想要设置的设备的属性字符串
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置Enum类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IEnumeration”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“IEnumeration”类型节点值，CL和CXP设备请参考接口：SciCam_SetEnumValueByStringEx
	#  @~english
	#  @brief Set Enum value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value, for example, using "PixelFormat" to set pixel format
	#  @param val		[IN]  Feature String to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting to the device, calling this interface allows you to set the value of a specific node of Enum type. The possible values for the "key" parameter can be referenced from the list of XML node parameter types, where the nodes with data type "IEnumeration" can be set using this interface. The "key" parameter value corresponds to the "Name" column in the list. \n
	#  		This interface is only used to set the values of "IEnumeration" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetEnumValueByStringEx.
	def SciCam_SetEnumValueByString(self, key, val):
		SciCamCtrlDll.SciCam_SetEnumValueByString.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_SetEnumValueByString.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetEnumValueByString(self.handle, key.encode('ascii'), val.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Command型属性值
	#  @param hDev		[IN]  设备句柄
	#  @param key		[IN]  属性键值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置指定的Command类型节点。key取值可以参考XML节点参数类型列表，表格里面数据类型为“ICommand”的节点都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“ICommand”类型节点值，CL和CXP设备请参考接口：SciCam_SetCommandValueEx
	#  @~english
	#  @brief Set Command value
	#  @param hDev		[IN]  Device handle
	#  @param key		[IN]  Key value
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified Command nodes. For value of strKey, see MvCameraNode. The node values of ICommand can be set through this interface, strKey value corresponds to the Name column.
	#  		This interface is only used to set the values of "ICommand" type nodes in the camera device XML. For CL and CXP devices, please refer to the interface: SciCam_SetCommandValueEx.
	def SciCam_SetCommandValue(self, key):
		SciCamCtrlDll.SciCam_SetCommandValue.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_SetCommandValue.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetCommandValue(self.handle, key.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 枚举节点集合
	#  @param hDev			[IN]      设备句柄
	#  @param nodes			[IN][OUT] 节点集，详细参考： @ref PSCI_CAM_NODE "PSCI_CAM_NODE"
	#  @param nodesCount	[IN][OUT] 节点个数
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 获取当前连接的设备所有节点集合，当nodes参数为空时，默认只返回当前节点个数
	#  @~english
	#  @brief Set Command value by xml type
	#  @param hDev			[IN]      Device handle
	#  @param nodes			[IN][OUT] Node collection, references: @ref PSCI_CAM_NODE "PSCI_CAM_NODE"
	#  @param nodesCount	[IN][OUT] Number of nodes
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks Retrieve the collection of all nodes for the currently connected device. When the nodes parameter is empty, it defaults to only returning the current number of nodes.
	def SciCam_GetNodes(self, nodes, nodesCount):
		SciCamCtrlDll.SciCam_GetNodes.argtypes = (ctypes.c_void_p, PSCI_CAM_NODE, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodes.restype = ctypes.c_uint
		if nodes == None:
			return SciCamCtrlDll.SciCam_GetNodes(self.handle, nodes, ctypes.byref(nodesCount))
		return SciCamCtrlDll.SciCam_GetNodes(self.handle, ctypes.byref(nodes), ctypes.byref(nodesCount))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点类型
	#  @param hDev			[IN]  设备句柄
	#  @param key			[IN]  属性键值
	#  @param pType			[OUT] 节点类型，详细参考： @ref SciCamNodeType "SciCamNodeType"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node type
	#  @param hDev			[IN]  Device handle
	#  @param key			[IN]  Attribute key value
	#  @param pType			[OUT] Node type, references: @ref SciCamNodeType "SciCamNodeType"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeType(self, key, pType):
		SciCamCtrlDll.SciCam_GetNodeType.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeType.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeType(self.handle, key.encode('ascii'), ctypes.byref(pType))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点命名空间
	#  @param hDev			[IN]  设备句柄
	#  @param key			[IN]  属性键值
	#  @param pNameSpace	[OUT] 节点命名空间，详细参考： @ref SciCamNodeNameSpace "SciCamNodeNameSpace"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node name space
	#  @param hDev			[IN]  Device handle
	#  @param key			[IN]  Attribute key value
	#  @param pNameSpace	[OUT] Node name space, references: @ref SciCamNodeNameSpace "SciCamNodeNameSpace"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeNameSpace(self, key, pNameSpace):
		SciCamCtrlDll.SciCam_GetNodeNameSpace.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeNameSpace.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeNameSpace(self.handle, key.encode('ascii'), ctypes.byref(pNameSpace))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点可见性
	#  @param hDev			[IN]  设备句柄
	#  @param key			[IN]  属性键值
	#  @param pVisibility	[OUT] 节点可见性，详细参考： @ref SciCamNodeVisibility "SciCamNodeVisibility"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node visibility
	#  @param hDev			[IN]  Device handle
	#  @param key			[IN]  Attribute key value
	#  @param pVisibility	[OUT] Node visibility, references: @ref SciCamNodeVisibility "SciCamNodeVisibility"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeVisibility(self, key, pVisibility):
		SciCamCtrlDll.SciCam_GetNodeVisibility.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeVisibility.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeVisibility(self.handle, key.encode('ascii'), ctypes.byref(pVisibility))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点访问模式
	#  @param hDev			[IN]  设备句柄
	#  @param key			[IN]  属性键值
	#  @param pAccessMode	[OUT] 节点访问模式，详细参考： @ref SciCamNodeAccessMode "SciCamNodeAccessMode"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node access mode
	#  @param hDev			[IN]  Device handle
	#  @param key			[IN]  Attribute key value
	#  @param pAccessMode	[OUT] Node access mode, references: @ref SciCamNodeAccessMode "SciCamNodeAccessMode"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeAccessMode(self, key, pAccessMode):
		SciCamCtrlDll.SciCam_GetNodeAccessMode.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeAccessMode.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeAccessMode(self.handle, key.encode('ascii'), ctypes.byref(pAccessMode))
	
	## @ingroup module_DeviceAttributeManipulation
	#  @~chinese
	#  @brief 导出相机属性到本地XML文件
	#  @param hDev			[IN]      设备句柄
	#  @param strFileName	[IN]      XML文件名
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以将设备属性导出到本地XML文件，strFileName为导出文件的路径和名称，CL和CXP设备请参考接口：@ref SciCam_FeatureSaveEx "SciCam_FeatureSaveEx"
	#  @~english
	#  @brief Export camera attribute to local XML file
	#  @param hDev			[IN]      Device handle
	#  @param strFileName	[IN]      XML file name
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting the device, call this interface to export the device attribute to a local XML file. strFileName is the path and name of the exported XML.
	def SciCam_FeatureSave(self, strFileName):
		SciCamCtrlDll.SciCam_FeatureSave.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_FeatureSave.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_FeatureSave(self.handle, strFileName.encode('ascii'))
	
	## @ingroup module_DeviceAttributeManipulation
	#  @~chinese
	#  @brief 从本地XML文件导入相机属性
	#  @param hDev			[IN]      设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以将本地XML文件导入设备属性，strFileName为导入文件的路径和名称，CL和CXP设备请参考接口：@ref SciCam_FeatureLoadEx "SciCam_FeatureLoadEx"
	#  @~english
	#  @brief Import camera attribute from local XML file
	#  @param hDev			[IN]      Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting the device, call this interface to import the device attribute from a local XML file. strFileName is the path and name of the imported XML.
	def SciCam_FeatureLoad(self, strFileName):
		SciCamCtrlDll.SciCam_FeatureLoad.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_FeatureLoad.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_FeatureLoad(self.handle, strFileName.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Integer属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值，如获取宽度信息则为"Width"
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_INT "PSCI_NODE_VAL_INT"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取int类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IInteger”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可获取设备XML中“IInteger”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Get Integer value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type，references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value, for example, using "Width" to get width
	#  @param pVal		[OUT] Structure pointer of camera features, references: PSCI_NODE_VAL_INT "PSCI_NODE_VAL_INT"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks You can call this API to get the value of camera node with integer type after connecting the device. For key value, refer to MvCameraNode. All the node values of "IInteger" in the list can be obtained via this API. Key corresponds to the Name column. \n
	#  		You can retrieve the values of "IInteger" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_GetIntValueEx(self, xmlType, key, pVal):
		SciCamCtrlDll.SciCam_GetIntValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, PSCI_NODE_VAL_INT)
		SciCamCtrlDll.SciCam_GetIntValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetIntValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Integer型属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值，如获取宽度信息则为"Width"
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置int类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IInteger”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可设置设备XML中“IInteger”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Set Integer value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value, for example, using "Width" to set width
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks You can call this API to get the value of camera node with integer type after connecting the device. For key value, refer to MvCameraNode. All the node values of "IInteger" in the list can be obtained via this API. Key corresponds to the Name column. \n
	#  		You can set the values of "IInteger" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetIntValueEx(self, xmlType, key, val):
		SciCamCtrlDll.SciCam_SetIntValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int64)
		SciCamCtrlDll.SciCam_SetIntValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetIntValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.c_int64(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Float属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_FLOAT "PSCI_NODE_VAL_FLOAT"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取float类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IFloat”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。
	#  		根据不同XML类型可获取设备XML中“IFloat”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Get Float value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value
	#  @param pVal		[OUT] Structure pointer of camera features, references: @ref PSCI_NODE_VAL_FLOAT "PSCI_NODE_VAL_FLOAT"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified float node. For detailed key value see: MvCameraNode. The node values of IFloat can be obtained through this interface, key value corresponds to the Name column. \n
	#  		You can retrieve the values of "IFloat" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_GetFloatValueEx(self, xmlType, key, pVal):
		SciCamCtrlDll.SciCam_GetFloatValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, PSCI_NODE_VAL_FLOAT)
		SciCamCtrlDll.SciCam_GetFloatValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetFloatValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置float型属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置float类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IFloat”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可设置设备XML中“IFloat”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Set float value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified float node. For detailed key value see: MvCameraNode. The node values of IFloat can be set through this interface, key value corresponds to the Name column. \n
	#  		You can set the values of "IFloat" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetFloatValueEx(self, xmlType, key, val):
		SciCamCtrlDll.SciCam_SetFloatValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_double)
		SciCamCtrlDll.SciCam_SetFloatValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetFloatValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.c_double(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Boolean属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pVal		[OUT] 返回给调用者有关设备属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取bool类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IBoolean”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可获取设备XML中“IBoolean”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Get Boolean value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value
	#  @param pVal		[OUT] Structure pointer of camera features
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified bool nodes. For value of key, see MvCameraNode. The node values of IBoolean can be obtained through this interface, key value corresponds to the Name column. \n
	#  		You can retrieve the values of "IFloat" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_GetBoolValueEx(self, xmlType, key, pVal):
		SciCamCtrlDll.SciCam_GetBoolValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetBoolValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetBoolValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Boolean型属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置bool类型的指定节点的值。strKey取值可以参考XML节点参数类型列表，表格里面数据类型为“IBoolean”的节点值都可以通过该接口设置，strKey参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可设置设备XML中“IBoolean”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Set Boolean value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified bool nodes. For value of key, see MvCameraNode. The node values of IBoolean can be set through this interface, key value corresponds to the Name column. \n
	#  		You can set the values of "IBoolean" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetBoolValueEx(self, xmlType, key, val):
		SciCamCtrlDll.SciCam_SetBoolValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_bool)
		SciCamCtrlDll.SciCam_SetBoolValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetBoolValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.c_bool(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取String属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取string类型的指定节点的值。Key取值可以参考XML节点参数类型列表，表格里面数据类型为“IString”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可获取设备XML中“IString”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Get String value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value
	#  @param pVal		[OUT] Structure pointer of camera features
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified string nodes. For value of key, see MvCameraNode. The node values of IString can be obtained through this interface, key value corresponds to the Name column. \n
	#  		You can retrieve the values of "IString" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_GetStringValueEx(self, xmlType, key, pVal):
		SciCamCtrlDll.SciCam_GetStringValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, PSCI_NODE_VAL_STRING)
		SciCamCtrlDll.SciCam_GetStringValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetStringValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置String型属性值（根据不同XML类型）
	#  @param hDev		[IN] 设备句柄
	#  @param xmlType	[IN] XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN] 属性键值
	#  @param val		[IN] 想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置string类型的指定节点的值。Key取值可以参考XML节点参数类型列表，表格里面数据类型为“IString”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可设置设备XML中“IString”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Set String value by xml type
	#  @param hDev		[IN] Device handle
	#  @param xmlType	[IN] XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN] Key value
	#  @param val		[IN] Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified string nodes. For value of key, see MvCameraNode. The node values of IString can be set through this interface, key value corresponds to the Name column.
	#  		You can set the values of "IString" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetStringValueEx(self, xmlType, key, val):
		SciCamCtrlDll.SciCam_SetStringValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_SetStringValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetStringValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), val.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取Enum属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值，如获取像素格式信息则为"PixelFormat"
	#  @param pVal		[OUT] 返回给调用者有关设备属性结构体指针，详细参考： @ref PSCI_NODE_VAL_ENUM "PSCI_NODE_VAL_ENUM"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以获取Enum类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IEnumeration”的节点值都可以通过该接口获取，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可获取设备XML中“IEnumeration”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Get Enum value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value, for example, using "PixelFormat" to get pixel format
	#  @param pVal		[OUT] Structure pointer of camera features, references: @ref PSCI_NODE_VAL_ENUM "PSCI_NODE_VAL_ENUM"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified Enum nodes. For value of key, see MvCameraNode, The node values of IEnumeration can be obtained through this interface, key value corresponds to the Name column. \n
	#  		You can retrieve the values of "IEnumeration" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_GetEnumValueEx(self, xmlType, key, pVal):
		SciCamCtrlDll.SciCam_GetEnumValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, PSCI_NODE_VAL_ENUM)
		SciCamCtrlDll.SciCam_GetEnumValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetEnumValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pVal))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Enum型属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值，如获取像素格式信息则为"PixelFormat"
	#  @param val		[IN]  想要设置的设备的属性值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置Enum类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IEnumeration”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可设置设备XML中“IEnumeration”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Set Enum value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value, for example, using "PixelFormat" to set pixel format
	#  @param val		[IN]  Feature value to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to get specified Enum nodes. For value of key, see MvCameraNode, The node values of IEnumeration can be obtained through this interface, key value corresponds to the Name column. \n
	#  		You can set the values of "IEnumeration" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetEnumValueEx(self, xmlType, key, val):
		SciCamCtrlDll.SciCam_SetEnumValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int64)
		SciCamCtrlDll.SciCam_SetEnumValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetEnumValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.c_int64(val))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Enum型属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值，如获取像素格式信息则为"PixelFormat"
	#  @param val		[IN]  想要设置的设备的属性字符串
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置Enum类型的指定节点的值。key取值可以参考XML节点参数类型列表，表格里面数据类型为“IEnumeration”的节点值都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		根据不同XML类型可设置设备XML中“IEnumeration”类型节点值，比如CL采集卡，xmlType为SciCamDeviceXmlType::SciCam_DeviceXml_Card
	#  @~english
	#  @brief Set Enum value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value, for example, using "PixelFormat" to set pixel format
	#  @param val		[IN]  Feature String to set
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting to the device, calling this interface allows you to set the value of a specific node of Enum type. The possible values for the "key" parameter can be referenced from the list of XML node parameter types, where the nodes with data type "IEnumeration" can be set using this interface. The "key" parameter value corresponds to the "Name" column in the list. \n
	#  		You can set the values of "IEnumeration" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetEnumValueByStringEx(self, xmlType, key, val):
		SciCamCtrlDll.SciCam_SetEnumValueByStringEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_SetEnumValueByStringEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetEnumValueByStringEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), val.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 设置Command型属性值（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以设置指定的Command类型节点。key取值可以参考XML节点参数类型列表，表格里面数据类型为“ICommand”的节点都可以通过该接口设置，key参数取值对应列表里面的“名称”一列。 \n
	#  		此接口仅用来设置相机设备XML中“ICommand”类型节点值，CL和CXP设备请参考接口：SciCam_SetCommandValueEx
	#  @~english
	#  @brief Set Command value by xml type
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Key value
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After the device is connected, call this interface to set specified Command nodes. For value of strKey, see MvCameraNode. The node values of ICommand can be set through this interface, strKey value corresponds to the Name column.
	#  		You can set the values of "ICommand" type nodes in the device XML based on different XML types. For example, for a CL capture card, the xmlType would be SciCamDeviceXmlType::SciCam_DeviceXml_Card.
	def SciCam_SetCommandValueEx(self, xmlType, key):
		SciCamCtrlDll.SciCam_SetCommandValueEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_SetCommandValueEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_SetCommandValueEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 枚举节点集合
	#  @param hDev			[IN]      设备句柄
	#  @param xmlType		[IN]      XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param nodes			[IN][OUT] 节点集，详细参考： @ref PSCI_CAM_NODE "PSCI_CAM_NODE"
	#  @param nodesCount	[IN][OUT] 节点个数
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 获取当前连接的设备所有节点集合
	#  @~english
	#  @brief Set Command value by xml type
	#  @param hDev			[IN]      Device handle
	#  @param xmlType		[IN]      XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param nodes			[IN][OUT] Node collection, references: @ref PSCI_CAM_NODE "PSCI_CAM_NODE"
	#  @param nodesCount	[IN][OUT] Number of nodes
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks Retrieve the collection of all nodes for the currently connected device.
	def SciCam_GetNodesEx(self, xmlType, nodes, nodesCount):
		SciCamCtrlDll.SciCam_GetNodesEx.argtypes = (ctypes.c_void_p, ctypes.c_int, PSCI_CAM_NODE, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodesEx.restype = ctypes.c_uint
		if nodes == None:
			return SciCamCtrlDll.SciCam_GetNodesEx(self.handle, ctypes.c_int(xmlType), nodes, ctypes.byref(nodesCount))
		return SciCamCtrlDll.SciCam_GetNodesEx(self.handle, ctypes.c_int(xmlType), ctypes.byref(nodes), ctypes.byref(nodesCount))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点类型（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pType		[OUT] 节点类型，详细参考： @ref SciCamNodeType "SciCamNodeType"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node type (based on different XML types)
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Attribute key value
	#  @param pType		[OUT] Node type, references: @ref SciCamNodeType "SciCamNodeType"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeTypeEx(self, xmlType, key, pType):
		SciCamCtrlDll.SciCam_GetNodeTypeEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeTypeEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeTypeEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pType))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点命名空间（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pNameSpace	[OUT] 节点命名空间，详细参考： @ref SciCamNodeNameSpace "SciCamNodeNameSpace"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node namespace (based on different XML types)
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Attribute key value
	#  @param pNameSpace	[OUT] Node namespace, references: @ref SciCamNodeNameSpace "SciCamNodeNameSpace"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeNameSpaceEx(self, xmlType, key, pNameSpace):
		SciCamCtrlDll.SciCam_GetNodeNameSpaceEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeNameSpaceEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeNameSpaceEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pNameSpace))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点可见性（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pVisibility	[OUT] 节点可见性，详细参考： @ref SciCamNodeVisibility "SciCamNodeVisibility"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node visibility (based on different XML types)
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Attribute key value
	#  @param pVisibility	[OUT] Node visibility, references: @ref SciCamNodeVisibility "SciCamNodeVisibility"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeVisibilityEx(self, xmlType, key, pVisibility):
		SciCamCtrlDll.SciCam_GetNodeVisibilityEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeVisibilityEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeVisibilityEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pVisibility))

	## @ingroup module_Node
	#  @~chinese
	#  @brief 获取节点访问模式（根据不同XML类型）
	#  @param hDev		[IN]  设备句柄
	#  @param xmlType	[IN]  XML类型，详细参考： @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  属性键值
	#  @param pAccessMode	[OUT] 节点访问模式，详细参考： @ref SciCamNodeAccessMode "SciCamNodeAccessMode"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Get node access mode (based on different XML types)
	#  @param hDev		[IN]  Device handle
	#  @param xmlType	[IN]  XML type, references: @ref SciCamDeviceXmlType "SciCamDeviceXmlType"
	#  @param key		[IN]  Attribute key value
	#  @param pAccessMode	[OUT] Node access mode, references: @ref SciCamNodeAccessMode "SciCamNodeAccessMode"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_GetNodeAccessModeEx(self, xmlType, key, pAccessMode):
		SciCamCtrlDll.SciCam_GetNodeAccessModeEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_GetNodeAccessModeEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_GetNodeAccessModeEx(self.handle, ctypes.c_int(xmlType), key.encode('ascii'), ctypes.byref(pAccessMode))

	## @ingroup module_DeviceAttributeManipulation
	#  @~chinese
	#  @brief 导出设备属性到本地XML文件
	#  @param hDev			[IN]      设备句柄
	#  @param xmlType		[IN]      XML文件类型
	#  @param strFileName	[IN]      XML文件名
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以将本地XML文件导出设备属性，strFileName为导出文件的路径和名称，xmlType为设备类型，支持CL和CXP设备
	#  @~english
	#  @brief Export device attribute to local XML file
	#  @param hDev			[IN]      Device handle
	#  @param xmlType		[IN]      XML file type
	#  @param strFileName	[IN]      XML file name
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting the device, call this interface to export the device attribute to a local XML file. strFileName is the path and name of the exported XML.
	#           xmlType is the type of the exported XML file, supporting CL and CXP devices.
	def SciCam_FeatureSaveEx(self, xmlType, strFileName):
		SciCamCtrlDll.SciCam_FeatureSaveEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_FeatureSaveEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_FeatureSaveEx(self.handle, ctypes.c_int(xmlType), strFileName.encode('ascii'))
	
	## @ingroup module_DeviceAttributeManipulation
	#  @~chinese
	#  @brief 从本地XML文件导入设备属性
	#  @param hDev			[IN]      设备句柄
	#  @param xmlType		[IN]      XML文件类型
	#  @param strFileName	[IN]      XML文件名
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 连接设备之后调用该接口可以将本地XML文件导入设备属性，strFileName为导入文件的路径和名称，xmlType为设备类型，支持CL和CXP设备
	#  @~english
	#  @brief Import device attribute from local XML file
	#  @param hDev			[IN]      Device handle
	#  @param xmlType		[IN]      XML file type
	#  @param strFileName	[IN]      XML file name
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retvalOther references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks After connecting the device, call this interface to import the device attribute from a local XML file. strFileName is the path and name of the imported XML.
	#           xmlType is the type of the imported XML file, supporting CL and CXP devices.
	def SciCam_FeatureLoadEx(self, xmlType, strFileName):
		SciCamCtrlDll.SciCam_FeatureLoadEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_FeatureLoadEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_FeatureLoadEx(self.handle, ctypes.c_int(xmlType), strFileName.encode('ascii'))

	## @ingroup module_Other
	#  @~chinese
	#  @brief 设置GigE设备IP、子网掩码和网关地址
	#  @param sn		[IN]  设备序列号
	#  @param ip		[IN]  ip地址
	#  @param mask		[IN]  子网掩码
	#  @param gateway	[IN]  网关
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks
	#  @~english
	#  @brief Open the camera devices connected to the CL capture card.
	#  @param sn		[IN]  Serial number
	#  @param ip		[IN]  ip
	#  @param mask		[IN]  mask
	#  @param gateway	[IN]  gateway
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks
	@staticmethod
	def SciCam_Gige_ModifyCamIp(sn, ip, mask, gateway):
		SciCamCtrlDll.SciCam_Gige_ModifyCamIp.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint)
		SciCamCtrlDll.SciCam_Gige_ModifyCamIp.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_Gige_ModifyCamIp(sn.encode('ascii'), ctypes.c_uint(ip), ctypes.c_uint(mask), ctypes.c_uint(gateway))

	## @ingroup module_Other
	#  @~chinese
	#  @brief 设置GigE设备IP、子网掩码和网关地址
	#  @param sn		[IN]  设备序列号
	#  @param ip		[IN]  ip地址，格式为字符串，如"192.168.1.100"
	#  @param mask		[IN]  子网掩码，格式为字符串，如"255.255.255.0"
	#  @param gateway	[IN]  网关，格式为字符串，如"192.168.1.1"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks
	#  @~english
	#  @brief Open the camera devices connected to the CL capture card.
	#  @param sn		[IN]  Serial number
	#  @param ip		[IN]  ip, e.g. "192.168.1.100"
	#  @param mask		[IN]  mask, e.g. "255.255.255.0"
	#  @param gateway	[IN]  gateway, e.g. "192.168.1.1"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks
	@staticmethod
	def SciCam_Gige_ModifyCamIpEx(sn, ip, mask, gateway):
		SciCamCtrlDll.SciCam_Gige_ModifyCamIpEx.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_Gige_ModifyCamIpEx.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_Gige_ModifyCamIpEx(sn.encode('ascii'), ip.encode('ascii'), mask.encode('ascii'), gateway.encode('ascii'))

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 打开CL采集卡连接的相机设备
	#  @param hDev		[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 只能对CL采集卡连接的相机进行操作
	#  @~english
	#  @brief Open the camera devices connected to the CL capture card.
	#  @param hDev		[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks Operations can only be performed on cameras connected to the CL capture card.
	def SciCam_CL_OpenCam(self):
		SciCamCtrlDll.SciCam_CL_OpenCam.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_CL_OpenCam.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_CL_OpenCam(self.handle)

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 关闭CL采集卡连接的相机设备
	#  @param hDev		[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 只能对CL采集卡连接的相机进行操作
	#  @~english
	#  @brief Disconnecting the Camera Device Connected to the CL Acquisition Card
	#  @param hDev		[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks Operations can only be performed on cameras connected to the CL capture card.
	def SciCam_CL_CloseCam(self):
		SciCamCtrlDll.SciCam_CL_CloseCam.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_CL_CloseCam.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_CL_CloseCam(self.handle)

	## @ingroup module_DeviceInitAndDestr
	#  @~chinese
	#  @brief 判断CL采集卡中的相机是否已连接
	#  @param hDev		[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks 只能对CL采集卡相连的相机进行操作
	#  @~english
	#  @brief Check if the camera in the CL capture card is connected.
	#  @param hDev		[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks Operations can only be performed on cameras connected to the CL capture card.
	def SciCam_CL_IsCamOpen(self):
		SciCamCtrlDll.SciCam_CL_IsCamOpen.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_CL_IsCamOpen.restype = ctypes.c_bool
		return SciCamCtrlDll.SciCam_CL_IsCamOpen(self.handle)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 设置采集类型（3D线扫激光轮廓设备）
	#  @param hDev		[IN]  设备句柄
	#  @param mode		[IN]  采集类型，详细参考： @ref SciCamLp3dGrabMode "SciCamLp3dGrabMode"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Set the grab type(3D LP camera)
	#  @param hDev		[IN]  Device handle
	#  @param mode		[IN]  Grab type, references: @ref SciCamLp3dGrabMode "SciCamLp3dGrabMode"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_LP3D_SetGrabType(self, mode):
		SciCamCtrlDll.SciCam_LP3D_SetGrabType.argtypes = (ctypes.c_void_p, ctypes.c_int)
		SciCamCtrlDll.SciCam_LP3D_SetGrabType.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_LP3D_SetGrabType(self.handle, ctypes.c_int(mode))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 开始录像
	#  @param hDev			[IN]  设备句柄
	#  @param recoredInfo	[IN]  录像信息，详细参考： @ref SCI_RECORD_INFO "SCI_RECORD_INFO"
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Start recording
	#  @param hDev			[IN]  Device handle
	#  @param recoredInfo	[IN]  Recording information, references: @ref SCI_RECORD_INFO "SCI_RECORD_INFO"
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_StartRecord(self, recordInfo):
		SciCamCtrlDll.SciCam_StartRecord.argtypes = (ctypes.c_void_p, PSCI_RECORD_INFO)
		SciCamCtrlDll.SciCam_StartRecord.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_StartRecord(self.handle, ctypes.byref(recordInfo))

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 传入录像数据
	#  @param hDev		[IN]  设备句柄
	#  @param payload	[IN]  采集到的payload数据
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Input recording data
	#  @param hDev		[IN]  Device handle
	#  @param payload	[IN]  Payload data captured
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_InputOneFrame(self, payload):
		SciCamCtrlDll.SciCam_InputOneFrame.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
		SciCamCtrlDll.SciCam_InputOneFrame.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_InputOneFrame(self.handle, payload)

	## @ingroup module_Grab
	#  @~chinese
	#  @brief 停止录像
	#  @param hDev		[IN]  设备句柄
	#  @retval 成功： @ref SCI_CAMERA_OK "SCI_CAMERA_OK"(0)
	#  @retval 其他参见: @ref SciCamErrorDefine.h "状态码"
	#  @remarks NULL
	#  @~english
	#  @brief Stop recording
	#  @param hDev		[IN]  Device handle
	#  @retval Success: @ref SCI_CAMERA_OK "SCI_CAMERA_OK"
	#  @retval Other references: @ref SciCamErrorDefine.h "Error Code List"
	#  @remarks NULL
	def SciCam_StopRecord(self):
		SciCamCtrlDll.SciCam_StopRecord.argtype = ctypes.c_void_p
		SciCamCtrlDll.SciCam_StopRecord.restype = ctypes.c_uint
		return SciCamCtrlDll.SciCam_StopRecord(self.handle)

class CameraOperation:
	def __init__(self, obj_cam, currentCam):
		self.obj_cam = obj_cam
		self.currentCam = currentCam

	def Open_Device(self):
		#self.obj_cam = SciCamera()
		self.obj_cam.SciCam_CreateDevice(self.currentCam)
		self.obj_cam.SciCam_OpenDevice()

		#SciCam_Grab
	def Start_Grabbing(self):
		reVal = self.obj_cam.SciCam_StartGrabbing()
