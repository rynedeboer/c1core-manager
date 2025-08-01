def _initialize_hardware(self):
        """Initialize hardware interfaces"""
        self.logger.info("Initializing Hardware Abstraction Layer")
        # In production, this would initialize actual hardware drivers
        self._simulated_data = {
            'external_voltage': 12.8,
            'internal_battery': 87.0,
            'cpu_temperature': 52.0,
            'interfaces': {},
            'can_messages': [],
            'gps_data': {'lat': 41.8781, 'lon': -87.6298, 'accuracy': 2.3}
        }
    
    async def read_external_voltage(self) -> float:
        """Read external voltage from ADC"""
        # Simulate voltage fluctuations
        base_voltage = self._simulated_data['external_voltage']
        variation = random.uniform(-0.3, 0.3)
        voltage = max(0, base_voltage + variation)
        self._simulated_data['external_voltage'] = voltage
        return voltage
    
    async def read_internal_battery_level(self) -> float:
        """Read internal battery level"""
        # Simulate battery discharge/charge
        current_level = self._simulated_data['internal_battery']
        change = random.uniform(-0.1, 0.2)  # Slight charging bias
        new_level = max(0, min(100, current_level + change))
        self._simulated_data['internal_battery'] = new_level
        return new_level
    
    async def read_cpu_temperature(self) -> float:
        """Read CPU temperature from thermal sensors"""
        # Simulate temperature variations
        base_temp = self._simulated_data['cpu_temperature']
        variation = random.uniform(-2, 2)
        temp = max(20, min(85, base_temp + variation))
        self._simulated_data['cpu_temperature'] = temp
        return temp
    
    async def test_interface(self, interface_name: str) -> bool:
        """Test specific hardware interface"""
        # Simulate interface testing with high success rate
        success_rates = {
            'can1': 0.95, 'can2': 0.95, 'cellular_modem': 0.98,
            'gps': 0.92, 'wifi': 0.85, 'bluetooth': 0.90,
            'ethernet_auto': 0.88, 'rs485': 0.93
        }
        rate = success_rates.get(interface_name, 0.80)
        return random.random() < rate
    
    async def control_led(self, led_name: str, state: str, frequency: float = 1.0):
        """Control LED indicators - CORE-021, CORE-022"""
        self.logger.debug(f"LED {led_name}: {state} @ {frequency}Hz")
        # In production, would control actual LED hardware
    
    async def set_component_power_state(self, component: str, state: str):
        """Set component power state"""
        self.logger.debug(f"Setting {component} power state to {state}")
        # In production, would control power management hardware
    
    async def read_can_message(self, bus: int) -> Optional[Dict]:
        """Read CAN message from specified bus"""
        # Simulate CAN message reception
        if random.random() < 0.1:  # 10% chance of message
            return {
                'bus': bus,
                'id': random.randint(0x100, 0x7FF),
                'data': [random.randint(0, 255) for _ in range(8)],
                'timestamp': time.time()
            }
        return None
    
    async def send_sms(self, number: str, message: str) -> bool:
        """Send SMS via cellular modem"""
        self.logger.info(f"Sending SMS to {number}: {message}")
        # In production, would use actual cellular modem
        return True


class DatabaseManager:
    """Database management for system configuration and logs"""
    
    def __init__(self, db_path: str = "/var/lib/c1core/system.db"):
        self.db_path = db_path
        self.logger = logger.getChild('Database')
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data TEXT
                );
                
                CREATE TABLE IF NOT EXISTS post_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id TEXT UNIQUE NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration REAL NOT NULL,
                    tests_passed INTEGER NOT NULL,
                    tests_failed INTEGER NOT NULL,
                    report TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS diagnostic_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    level TEXT NOT NULL,
                    duration REAL NOT NULL,
                    tests_passed INTEGER NOT NULL,
                    tests_failed INTEGER NOT NULL,
                    report TEXT NOT NULL
                );
            """)
        
        self.logger.info("Database initialized successfully")
    
    def save_config(self, key: str, value: Any):
        """Save configuration value"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
    
    def get_config(self, key: str, default=None):
        """Get configuration value"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT value FROM system_config WHERE key = ?", (key,)
            ).fetchone()
            
            if result:
                return json.loads(result[0])
            return default
    
    def log_event(self, level: str, source: str, message: str, data: Dict = None):
        """Log system event"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO system_events (level, source, message, data) VALUES (?, ?, ?, ?)",
                (level, source, message, json.dumps(data) if data else None)
            )
    
    def save_post_result(self, post_result: POSTResult):
        """Save POST test results"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO post_results (test_id, duration, tests_passed, tests_failed, report) VALUES (?, ?, ?, ?, ?)",
                (post_result.test_id, post_result.duration, post_result.tests_passed, 
                 post_result.tests_failed, json.dumps(post_result.generate_report()))
            )


class C1CoreDeviceManager:
    """
    Main device management system for Morey C1-Core
    Implements requirements from SRS and Device Management SFR
    """
    
    def __init__(self):
        self.logger = logger.getChild('DeviceManager')
        
        # Core system state
        self.current_state = SystemState.ACTIVE
        self.last_reset_reason = ResetReason.POWER_ON_RESET
        self.start_time = time.time()
        self.running = False
        self.shutdown_requested = False
        
        # Hardware and database interfaces
        self.hal = HardwareAbstractionLayer()
        self.db = DatabaseManager()
        
        # System monitoring
        self.system_health = SystemHealth(
            cpu_usage=0, memory_usage=0, cpu_temperature=25.0,
            external_voltage=12.0, internal_battery_level=100.0,
            power_consumption_ua=PowerLevel.ACTIVE_MAX,
            uptime_seconds=0, timestamp=datetime.now()
        )
        
        # Interface and container management
        self.interfaces = {}
        self.docker_containers = {}
        self.wake_up_callbacks = {}
        
        # Threading and state management
        self.monitoring_thread = None
        self.web_server = None
        self.state_transition_lock = threading.Lock()
        
        # Configuration
        self.config = self._load_system_config()
        
        # Initialize interfaces
        self._init_interfaces()
        
        self.logger.info("C1-Core Device Manager initialized")
    
    def _load_system_config(self) -> Dict:
        """Load system configuration from database"""
        config = {
            'voltage_thresholds': {
                '12v_min': 9.6,
                '24v_min': 19.2
            },
            'power_timeouts': {
                'low_power_delay': 60,
                'shutdown_delay': 300
            },
            'monitoring_intervals': {
                'health_check': 5,
                'interface_check': 10,
                'container_check': 15
            },
            'cellular': {
                'apn': 'internet.provider.com',
                'timeout': 30
            },
            'wifi': {
                'max_ssids': 8,
                'max_clients_per_ssid': 16
            }
        }
        
        # Load from database if available
        for key in config:
            stored_value = self.db.get_config(key)
            if stored_value:
                config[key] = stored_value
        
        return config
    
    def _init_interfaces(self):
        """Initialize interface status tracking"""
        interface_names = [
            'cellular_modem', 'gps', 'wifi', 'bluetooth', 
            'can1', 'can2', 'ethernet_auto', 'ethernet_ind', 
            'rs485', 'digital_inputs', 'analog_inputs'
        ]
        
        for name in interface_names:
            self.interfaces[name] = InterfaceStatus(name, False, None)
    
    async def power_on_self_test(self) -> POSTResult:
        """
        Comprehensive Power-On Self Test - CORE-010 to CORE-023
        Must complete in 10 seconds or less - CORE-020
        """
        self.logger.info("Starting Power-On Self Test (POST)")
        self.current_state = SystemState.POST_RUNNING
        
        post_result = POSTResult()
        start_time = time.time()
        
        try:
            # External voltage test - CORE-011
            voltage = await self.hal.read_external_voltage()
            post_result.add_test_result(
                "EXTERNAL_VOLTAGE", 
                9.0 <= voltage <= 36.0,
                f"Voltage: {voltage:.2f}V",
                voltage
            )
            
            # Internal power test - CORE-012
            battery_level = await self.hal.read_internal_battery_level()
            post_result.add_test_result(
                "INTERNAL_POWER",
                battery_level > 20,
                f"Battery: {battery_level:.1f}%",
                battery_level
            )
            
            # OS integrity test - CORE-013
            os_files_ok = all([
                os.path.exists('/bin/sh'),
                os.path.exists('/etc/passwd'),
                os.path.exists('/proc/version')
            ])
            post_result.add_test_result(
                "OS_INTEGRITY",
                os_files_ok,
                "Critical OS files verified" if os_files_ok else "Missing OS files"
            )
            
            # RAM connectivity test - CORE-014
            mem_info = psutil.virtual_memory()
            ram_ok = mem_info.total >= SystemConstants.MIN_RAM_GB * 1024**3
            post_result.add_test_result(
                "RAM_CONNECTIVITY",
                ram_ok,
                f"RAM: {mem_info.total // (1024**3)}GB available",
                mem_info.total // (1024**3)
            )
            
            # FLASH memory test - CORE-015
            disk_usage = psutil.disk_usage('/')
            flash_ok = disk_usage.total >= SystemConstants.MIN_PROGRAM_FLASH_MB * 1024**2
            post_result.add_test_result(
                "FLASH_MEMORY",
                flash_ok,
                f"Flash: {disk_usage.total // (1024**2)}MB available",
                disk_usage.total // (1024**2)
            )
            
            # Asset communication interfaces test - CORE-016
            for interface in ['can1', 'can2', 'ethernet_auto', 'rs485']:
                status = await self.hal.test_interface(interface)
                post_result.add_test_result(
                    f"ASSET_COMM_{interface.upper()}",
                    status,
                    "Interface responsive" if status else "Interface not responding"
                )
            
            # Wireless modules test - CORE-017
            for module in ['wifi', 'bluetooth']:
                status = await self.hal.test_interface(module)
                post_result.add_test_result(
                    f"WIRELESS_{module.upper()}",
                    status,
                    "Module responsive" if status else "Module not responding"
                )
            
            # Peripherals test - CORE-018
            peripherals = ['rtc', 'tpm', 'lpm', 'imu', 'gps', 'cellular_modem']
            for peripheral in peripherals:
                status = await self.hal.test_interface(peripheral)
                post_result.add_test_result(
                    f"PERIPHERAL_{peripheral.upper()}",
                    status,
                    "Peripheral responsive" if status else "Peripheral not responding"
                )
            
            post_result.duration = time.time() - start_time
            
            # LED indication - CORE-021, CORE-022
            if post_result.is_successful():
                await self.hal.control_led('all', 'blink', 0.5)
                await asyncio.sleep(3)
                self.logger.info(f"POST completed successfully in {post_result.duration:.2f} seconds")
            else:
                await self.hal.control_led('all', 'blink', 2.0)
                await asyncio.sleep(5)
                self.logger.error(f"POST failed with {post_result.tests_failed} failures")
            
            # Save POST results - CORE-023
            self.db.save_post_result(post_result)
            
            # Log event
            self.db.log_event(
                'info' if post_result.is_successful() else 'error',
                'POST',
                f"POST completed: {post_result.tests_passed}/{post_result.tests_passed + post_result.tests_failed} tests passed",
                post_result.generate_report()
            )
            
            return post_result
            
        except Exception as e:
            post_result.duration = time.time() - start_time
            post_result.add_test_result("POST_EXECUTION", False, str(e))
            self.logger.error(f"POST execution failed: {e}")
            return post_result
        finally:
            self.current_state = SystemState.ACTIVE
    
    async def start_system(self):
        """Start the complete device management system"""
        self.logger.info("Starting C1-Core Device Management System")
        
        try:
            # Create necessary directories
            for directory in [SystemConstants.CONFIG_DIR, SystemConstants.DATA_DIR, SystemConstants.LOG_DIR]:
                directory.mkdir(exist_ok=True, parents=True)
            
            # Perform POST first
            post_result = await self.power_on_self_test()
            
            if not post_result.is_successful():
                self.logger.warning("POST failed, continuing with limited functionality")
            
            # Start required services - DEVMGMT-003
            await self._start_core_services()
            
            # Initialize essential applications - CORE-031
            await self._start_essential_applications()
            
            # Start monitoring systems
            self.running = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            # Start web server for UI
            await self._start_web_server()
            
            # Set up signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            self.logger.info("Device Management System started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start system: {e}")
            raise
    
    async def _start_core_services(self):
        """Start core system services - DEVMGMT-003"""
        services = [
            'firmware_update_service',
            'diagnostics_service', 
            'database_service',
            'middleware_service'
        ]
        
        for service in services:
            try:
                self.logger.info(f"Starting {service}")
                # In production, would start actual services
                await asyncio.sleep(0.1)  # Simulate startup time
            except Exception as e:
                self.logger.error(f"Failed to start {service}: {e}")
    
    async def _start_essential_applications(self):
        """Start essential Morey applications - CORE-031"""
        essential_apps = [
            {'name': 'morey-essential', 'essential': True},
            {'name': 'vehicle-asset-comm', 'essential': True},
            {'name': 'gnss-location', 'essential': True},
            {'name': 'cellular-comm', 'essential': True},
            {'name': 'ble-monitor', 'essential': True},
            {'name': 'can-interface', 'essential': True}
        ]
        
        for app in essential_apps:
            try:
                await self._start_docker_application(app['name'], app['essential'])
            except Exception as e:
                self.logger.error(f"Failed to start essential app {app['name']}: {e}")
    
    async def _start_docker_application(self, app_name: str, essential: bool = False):
        """Start application in docker container - DEVMGMT-021 to DEVMGMT-025"""
        try:
            container_info = ContainerInfo(
                name=app_name,
                status='running',
                essential=essential,
                memory_usage_mb=random.uniform(10, 50),
                storage_usage_mb=random.uniform(50, 200),
                cpu_usage=random.uniform(1, 10),
                start_time=datetime.now()
            )
            
            self.docker_containers[app_name] = container_info
            self.logger.info(f"Started docker application: {app_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to start docker application {app_name}: {e}")
            raise
    
    def _monitoring_loop(self):
        """Main monitoring loop - DEVMGMT-005, DEVMGMT-006"""
        self.logger.info("Starting system monitoring loop")
        
        while self.running and not self.shutdown_requested:
            try:
                # Update system health
                asyncio.run(self._update_system_health())
                
                # Monitor interfaces
                self._monitor_interfaces()
                
                # Monitor docker containers
                self._monitor_docker_containers()
                
                # Check state transitions
                self._check_state_transitions()
                
                # Monitor for wake signals
                self._check_wake_signals()
                
                time.sleep(self.config['monitoring_intervals']['health_check'])
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)
    
    async def _update_system_health(self):
        """Update comprehensive system health metrics"""
        try:
            # CPU and memory
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Hardware readings
            cpu_temp = await self.hal.read_cpu_temperature()
            ext_voltage = await self.hal.read_external_voltage()
            batt_level = await self.hal.read_internal_battery_level()
            
            # Power consumption based on current state
            power_consumption = self._calculate_power_consumption()
            
            # Update system health
            self.system_health = SystemHealth(
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                cpu_temperature=cpu_temp,
                external_voltage=ext_voltage,
                internal_battery_level=batt_level,
                power_consumption_ua=power_consumption,
                uptime_seconds=int(time.time() - self.start_time),
                timestamp=datetime.now()
            )
            
            # Check health thresholds
            self._check_health_thresholds()
            
        except Exception as e:
            self.logger.error(f"Failed to update system health: {e}")
    
    def _calculate_power_consumption(self) -> int:
        """Calculate current power consumption based on system state"""
        base_consumption = {
            SystemState.ACTIVE: PowerLevel.ACTIVE_MAX,
            SystemState.LOW_POWER: PowerLevel.LOW_POWER_MAX,
            SystemState.INTERNAL_BATTERY_ONLY: PowerLevel.INTERNAL_BATTERY_MAX,
            SystemState.STORAGE_MODE: PowerLevel.STORAGE_MODE_MAX,
            SystemState.SHUTDOWN: 0
        }
        
        return base_consumption.get(self.current_state, PowerLevel.ACTIVE_MAX)
    
    def _check_health_thresholds(self):
        """Check health thresholds and generate events"""
        health = self.system_health
        
        # CPU threshold
        if health.cpu_usage > 90:
            self._generate_health_event('warning', 'cpu_high', f'CPU usage: {health.cpu_usage:.1f}%')
        
        # Memory threshold
        if health.memory_usage > 85:
            self._generate_health_event('warning', 'memory_high', f'Memory usage: {health.memory_usage:.1f}%')
        
        # Temperature threshold
        if health.cpu_temperature > SystemConstants.TEMP_MAX_C:
            self._generate_health_event('error', 'temperature_high', f'CPU temp: {health.cpu_temperature:.1f}°C')
        
        # Voltage thresholds
        if health.external_voltage < self.config['voltage_thresholds']['12v_min']:
            self._generate_health_event('warning', 'voltage_low', f'External voltage: {health.external_voltage:.1f}V')
        
        # Battery threshold
        if health.internal_battery_level < 20:
            self._generate_health_event('warning', 'battery_low', f'Battery: {health.internal_battery_level:.1f}%')
    
    def _generate_health_event(self, level: str, event_type: str, message: str):
        """Generate health monitoring event"""
        self.logger.log(
            getattr(logging, level.upper()),
            f"HEALTH EVENT - {event_type}: {message}"
        )
        self.db.log_event(level, 'health_monitor', message, {'event_type': event_type})
    
    async def run_diagnostics(self, level: DiagnosticLevel) -> Dict:
        """Run comprehensive diagnostic tests - CORE-025"""
        self.logger.info(f"Running {level.value} diagnostics")
        
        start_time = time.time()
        results = {
            'level': level.value,
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'summary': {}
        }
        
        try:
            if level in [DiagnosticLevel.BASIC, DiagnosticLevel.MEDIUM, DiagnosticLevel.ADVANCED]:
                # Basic diagnostics
                basic_tests = await self._run_basic_diagnostics()
                results['tests'].extend(basic_tests)
            
            if level in [DiagnosticLevel.MEDIUM, DiagnosticLevel.ADVANCED]:
                # Medium diagnostics
                medium_tests = await self._run_medium_diagnostics()
                results['tests'].extend(medium_tests)
            
            if level == DiagnosticLevel.ADVANCED:
                # Advanced diagnostics
                advanced_tests = await self._run_advanced_diagnostics()
                results['tests'].extend(advanced_tests)
            
            # Calculate summary
            total_tests = len(results['tests'])
            passed_tests = sum(1 for test in results['tests'] if test['result'] == 'pass')
            failed_tests = total_tests - passed_tests
            duration = time.time() - start_time
            
            results['summary'] = {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'duration_seconds': round(duration, 2),
                'success_rate': round((passed_tests / max(1, total_tests)) * 100, 1)
            }
            
            # Save results
            self.db.execute(
                "INSERT INTO diagnostic_results (level, duration, tests_passed, tests_failed, report) VALUES (?, ?, ?, ?, ?)",
                (level.value, duration, passed_tests, failed_tests, json.dumps(results))
            )
            
            self.logger.info(f"Diagnostics completed: {passed_tests}/{total_tests} tests passed")
            return results
            
        except Exception as e:
            self.logger.error(f"Diagnostic execution failed: {e}")
            results['error'] = str(e)
            return results
    
    async def _start_web_server(self):
        """Start web server for UI communication"""
        app = web.Application()
        
        # Enable CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # API routes
        app.router.add_get('/api/status', self._api_get_status)
        app.router.add_post('/api/diagnostics', self._api_run_diagnostics)
        app.router.add_post('/api/config', self._api_update_config)
        app.router.add_post('/api/control/{action}', self._api_control_action)
        app.router.add_get('/api/logs', self._api_get_logs)
        
        # Add CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)
        
        # Static file serving (for the UI)
        app.router.add_static('/', path='static/', name='static')
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        
        self.logger.info("Web server started on http://0.0.0.0:8080")
    
    async def _api_get_status(self, request):
        """API endpoint to get system status"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'state': self.current_state.value,
            'last_reset_reason': self.last_reset_reason.value,
            'system_health': self.system_health.to_dict(),
            'interfaces': {name: iface.to_dict() for name, iface in self.interfaces.items()},
            'containers': {name: container.to_dict() for name, container in self.docker_containers.items()},
            'uptime_seconds': int(time.time() - self.start_time)
        }
        return web.json_response(status)
    
    async def _api_run_diagnostics(self, request):
        """API endpoint to run diagnostics"""
        data = await request.json()
        level = DiagnosticLevel(data.get('level', 'basic'))
        results = await self.run_diagnostics(level)
        return web.json_response(results)
    
    async def _api_update_config(self, request):
        """API endpoint to update configuration"""
        try:
            config_data = await request.json()
            name = config_data.get('name')
            data = config_data.get('data')
            
            if not name or not data:
                return web.json_response({'error': 'Missing name or data'}, status=400)
            
            # Validate JSON format
            if isinstance(data, str):
                data = json.loads(data)
            
            # Save configuration
            self.db.save_config(name, data)
            
            # Apply configuration if it's a known config type
            await self._apply_configuration(name, data)
            
            self.logger.info(f"Configuration '{name}' updated successfully")
            return web.json_response({'success': True, 'message': f'Configuration {name} updated'})
            
        except Exception as e:
            self.logger.error(f"Configuration update failed: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def controlled_shutdown(self):
        """Perform controlled system shutdown - DEVMGMT-009 to DEVMGMT-015"""
        self.logger.info("Initiating controlled system shutdown")
        
        self.shutdown_requested = True
        
        try:
            # Notify all processes - DEVMGMT-010
            await self._notify_shutdown()
            
            # Wait for cleanup - DEVMGMT-011
            await asyncio.sleep(5)
            
            # Stop services - DEVMGMT-012
            await self._stop_services()
            
            # Save system state - DEVMGMT-013
            await self._save_system_state()
            
            # Release resources - DEVMGMT-014
            await self._release_resources()
            
            self.current_state = SystemState.SHUTDOWN
            self.logger.info("Controlled shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self.running = False
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status for API"""
        return {
            'timestamp': datetime.now().isoformat(),
            'device_info': {
                'model': 'C1-Core',
                'version': '1.0.0',
                'serial_number': 'C1C-2025-001',
                'build_date': '2025-01-01'
            },
            'state': self.current_state.value,
            'last_reset_reason': self.last_reset_reason.value,
            'system_health': self.system_health.to_dict(),
            'interfaces': {name: iface.to_dict() for name, iface in self.interfaces.items()},
            'containers': {name: container.to_dict() for name, container in self.docker_containers.items()},
            'power_consumption_ua': self._calculate_power_consumption(),
            'uptime_seconds': int(time.time() - self.start_time),
            'configuration': self.config
        }


async def main():
    """Main function to run the device manager"""
    device_manager = C1CoreDeviceManager()
    
    try:
        # Start the complete system
        await device_manager.start_system()
        
        # Keep the system running
        while device_manager.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"System error: {e}")
    finally:
        await device_manager.controlled_shutdown()


class DeviceManagerAPI:
    """Extended API functionality for advanced device management"""
    
    def __init__(self, device_manager: C1CoreDeviceManager):
        self.device_manager = device_manager
        self.logger = logger.getChild('API')
    
    async def handle_ota_update(self, update_data: Dict) -> Dict:
        """Handle Over-The-Air updates - CORE-163 to CORE-167"""
        try:
            update_type = update_data.get('type')  # firmware, application, configuration
            update_file = update_data.get('file_path')
            update_hash = update_data.get('hash')
            
            self.logger.info(f"Processing OTA update: {update_type}")
            
            # Verify update integrity
            if not await self._verify_update_integrity(update_file, update_hash):
                raise ValueError("Update integrity verification failed")
            
            # Create backup
            backup_id = await self._create_system_backup()
            
            # Apply update based on type
            if update_type == 'firmware':
                result = await self._apply_firmware_update(update_file)
            elif update_type == 'application':
                result = await self._apply_application_update(update_file)
            elif update_type == 'configuration':
                result = await self._apply_configuration_update(update_file)
            else:
                raise ValueError(f"Unknown update type: {update_type}")
            
            return {
                'success': True,
                'update_type': update_type,
                'backup_id': backup_id,
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"OTA update failed: {e}")
            # Attempt rollback if backup exists
            if 'backup_id' in locals():
                await self._rollback_update(backup_id)
            return {'success': False, 'error': str(e)}
    
    async def _verify_update_integrity(self, file_path: str, expected_hash: str) -> bool:
        """Verify update file integrity using SHA-256"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            actual_hash = sha256_hash.hexdigest()
            return actual_hash == expected_hash
            
        except Exception as e:
            self.logger.error(f"Hash verification failed: {e}")
            return False
    
    async def handle_remote_diagnostics(self, command: str) -> Dict:
        """Handle remote diagnostic commands - CORE-024"""
        self.logger.info(f"Processing remote diagnostic command: {command}")
        
        try:
            if 'basic' in command.lower():
                results = await self.device_manager.run_diagnostics(DiagnosticLevel.BASIC)
            elif 'medium' in command.lower():
                results = await self.device_manager.run_diagnostics(DiagnosticLevel.MEDIUM)
            elif 'advanced' in command.lower():
                results = await self.device_manager.run_diagnostics(DiagnosticLevel.ADVANCED)
            else:
                # Default to basic diagnostics
                results = await self.device_manager.run_diagnostics(DiagnosticLevel.BASIC)
            
            # Send results via SMS or cellular data
            await self._send_diagnostic_results(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Remote diagnostics failed: {e}")
            return {'error': str(e)}
    
    async def _send_diagnostic_results(self, results: Dict):
        """Send diagnostic results via cellular communication"""
        try:
            # Send summary via SMS for quick overview
            summary = results.get('summary', {})
            sms_message = f"Diagnostics: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)} tests passed"
            
            # In production, would use actual SMS capability
            self.logger.info(f"Sending diagnostic SMS: {sms_message}")
            
            # Send full results via data connection to cloud
            # In production, would send to AWS IoT or similar service
            self.logger.info("Sending full diagnostic results to cloud")
            
        except Exception as e:
            self.logger.error(f"Failed to send diagnostic results: {e}")


class SecurityManager:
    """Security management for C1-Core device - CORE-005, CORE-044 to CORE-049"""
    
    def __init__(self):
        self.logger = logger.getChild('Security')
        self._init_security_policies()
    
    def _init_security_policies(self):
        """Initialize security policies and firewall rules"""
        self.logger.info("Initializing security policies")
        
        # Firewall rules - CORE-045
        self._setup_firewall_rules()
        
        # TLS configuration - CORE-049, CORE-164
        self._setup_tls_config()
        
        # Authentication setup - CORE-005
        self._setup_authentication()
    
    def _setup_firewall_rules(self):
        """Setup firewall rules to drop incoming connections - CORE-045"""
        firewall_rules = [
            "iptables -P INPUT DROP",
            "iptables -P FORWARD DROP", 
            "iptables -P OUTPUT ACCEPT",
            "iptables -A INPUT -i lo -j ACCEPT",
            "iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT"
        ]
        
        for rule in firewall_rules:
            self.logger.debug(f"Firewall rule: {rule}")
            # In production, would execute actual iptables commands
    
    def _setup_tls_config(self):
        """Setup TLS 1.2+ configuration for secure communications"""
        tls_config = {
            'min_version': 'TLSv1.2',
            'cipher_suites': [
                'ECDHE-RSA-AES256-GCM-SHA384',
                'ECDHE-RSA-AES128-GCM-SHA256',
                'ECDHE-RSA-AES256-SHA384',
                'ECDHE-RSA-AES128-SHA256'
            ],
            'certificate_validation': True,
            'hostname_verification': True
        }
        
        self.logger.info("TLS configuration initialized")
        return tls_config
    
    def _setup_authentication(self):
        """Setup RSA/AES authentication for secure boot - CORE-005"""
        auth_config = {
            'rsa_key_size': 2048,
            'aes_key_size': 256,
            'sha_algorithm': 'SHA256',
            'secure_boot_enabled': True
        }
        
        self.logger.info("Authentication system initialized")
        return auth_config
    
    def validate_ota_signature(self, file_path: str, signature: str, public_key: str) -> bool:
        """Validate OTA update signature for secure updates"""
        try:
            # In production, would use actual cryptographic verification
            self.logger.info(f"Validating OTA signature for {file_path}")
            
            # Simulate signature validation
            import hashlib
            file_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                file_hash.update(f.read())
            
            # In production, would verify RSA signature with public key
            return True  # Simulated validation
            
        except Exception as e:
            self.logger.error(f"Signature validation failed: {e}")
            return False


class LocationManager:
    """GNSS location management - CORE-035 to CORE-039"""
    
    def __init__(self, hal: HardwareAbstractionLayer):
        self.hal = hal
        self.logger = logger.getChild('Location')
        self.current_location = None
        self.satellite_info = {
            'gps': 0, 'glonass': 0, 'beidou': 0, 'galileo': 0
        }
        self.accuracy_meters = 10.0
    
    async def get_current_location(self) -> Optional[Dict]:
        """Get current GNSS location with constellation support - CORE-037"""
        try:
            # Simulate GNSS data acquisition
            location_data = {
                'latitude': 41.8781 + random.uniform(-0.001, 0.001),
                'longitude': -87.6298 + random.uniform(-0.001, 0.001),
                'altitude': 180.0 + random.uniform(-5, 5),
                'accuracy_meters': random.uniform(1.0, 5.0),
                'timestamp': datetime.now().isoformat(),
                'satellites': {
                    'gps': random.randint(6, 12),
                    'glonass': random.randint(0, 8),
                    'beidou': random.randint(0, 6),
                    'galileo': random.randint(0, 4)
                },
                'hdop': random.uniform(0.8, 2.0),
                'fix_quality': 'GPS' if random.random() > 0.1 else 'DGPS'
            }
            
            # Verify accuracy requirement - CORE-038 (10ft / 3m accuracy)
            if location_data['accuracy_meters'] <= 3.0:
                self.current_location = location_data
                self.logger.debug(f"Location updated: {location_data['latitude']:.6f}, {location_data['longitude']:.6f}")
                return location_data
            else:
                self.logger.warning(f"Location accuracy poor: {location_data['accuracy_meters']:.1f}m")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get location: {e}")
            return None
    
    def get_satellite_status(self) -> Dict:
        """Get satellite constellation status"""
        total_satellites = sum(self.satellite_info.values())
        return {
            'total_satellites': total_satellites,
            'constellations': self.satellite_info,
            'accuracy': self.accuracy_meters,
            'last_update': datetime.now().isoformat()
        }


# Additional utility classes and functions

class ContainerOrchestrator:
    """Docker container orchestration for applications - DEVMGMT-021 to DEVMGMT-025"""
    
    def __init__(self):
        self.logger = logger.getChild('Containers')
        self.containers = {}
    
    async def start_container(self, name: str, image: str, essential: bool = False) -> bool:
        """Start a docker container"""
        try:
            # Simulate docker container start
            self.logger.info(f"Starting container: {name} from image {image}")
            
            container_info = ContainerInfo(
                name=name,
                status='running',
                essential=essential,
                memory_usage_mb=random.uniform(10, 100),
                storage_usage_mb=random.uniform(50, 500),
                cpu_usage=random.uniform(1, 20),
                start_time=datetime.now()
            )
            
            self.containers[name] = container_info
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start container {name}: {e}")
            return False
    
    async def stop_container(self, name: str) -> bool:
        """Stop a docker container"""
        try:
            if name in self.containers:
                self.containers[name].status = 'stopped'
                self.logger.info(f"Stopped container: {name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to stop container {name}: {e}")
            return False
    
    async def restart_container(self, name: str) -> bool:
        """Restart a docker container"""
        try:
            if name in self.containers:
                await self.stop_container(name)
                await asyncio.sleep(1)
                self.containers[name].status = 'running'
                self.containers[name].start_time = datetime.now()
                self.containers[name].restart_count += 1
                self.logger.info(f"Restarted container: {name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to restart container {name}: {e}")
            return False
    
    def get_container_stats(self) -> Dict:
        """Get container statistics"""
        stats = {
            'total_containers': len(self.containers),
            'running_containers': len([c for c in self.containers.values() if c.status == 'running']),
            'essential_containers': len([c for c in self.containers.values() if c.essential]),
            'total_memory_mb': sum(c.memory_usage_mb for c in self.containers.values()),
            'containers': {name: container.to_dict() for name, container in self.containers.items()}
        }
        return stats


def create_startup_script():
    """Create systemd service file for automatic startup"""
    service_content = """[Unit]
Description=Morey C1-Core Device Manager
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/c1core
ExecStart=/usr/bin/python3 /opt/c1core/device_manager.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    service_path = "/etc/systemd/system/c1core-device-manager.service"
    try:
        with open(service_path, 'w') as f:
            f.write(service_content)
        
        # Enable and start service
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', 'c1core-device-manager'], check=True)
        
        logger.info("Systemd service created and enabled")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create startup script: {e}")
        return False


if __name__ == "__main__":
    """Main entry point for the C1-Core Device Manager"""
    
    # Print startup banner
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║        🚛 MOREY C1-CORE DEVICE MANAGER v1.0.0               ║
    ║                                                              ║
    ║        Advanced Telematics Platform                          ║
    ║        Light & Heavy Duty Vehicles                           ║
    ║                                                              ║
    ║        SRS Version: 00.01.00                                 ║
    ║        Device Management SFR: 00.00.01                       ║
    ║                                                              ║
    ║        Copyright © 2025 Morey Corporation                    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Check if running as root (required for hardware access)
        if os.geteuid() != 0:
            print("Warning: Not running as root. Some hardware features may not work.")
        
        # Create startup service if requested
        if '--install-service' in sys.argv:
            if create_startup_script():
                print("✅ Systemd service installed successfully")
                print("   Use 'systemctl start c1core-device-manager' to start")
                exit(0)
            else:
                print("❌ Failed to install systemd service")
                exit(1)
        
        # Run the device manager
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Device Manager stopped by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        exit(1)
#!/usr/bin/env python3
"""
Morey C1-Core Device Manager - Complete Implementation
Advanced telematics device management system for light and heavy duty vehicles.
Implements requirements from SRS Version 00.01.00 and Device Management SFR Version 00.00.01

This is the complete implementation including:
- Web API server for UI communication
- Hardware abstraction layer
- Real-time monitoring and control
- OTA update management
- Docker container orchestration
- Complete logging and diagnostics

Author: Morey Corporation
Version: 1.0.0
Date: 2025
"""

import asyncio
import json
import logging
import threading
import time
import signal
import os
import subprocess
import psutil
import sqlite3
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import uuid

# Web server imports
from aiohttp import web, WSMsgType
from aiohttp.web import Application, Response
import aiohttp_cors

# Hardware simulation imports (replace with actual hardware drivers)
import random
import struct

# Configure comprehensive logging
def setup_logging():
    """Setup comprehensive logging system"""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Create logs directory
    log_dir = Path('/var/log/c1core')
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # File handler for all logs
    file_handler = logging.FileHandler(log_dir / 'device_manager.log')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler for info and above
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Error handler for critical issues
    error_handler = logging.FileHandler(log_dir / 'errors.log')
    error_handler.setFormatter(log_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_handler)
    
    return logging.getLogger('C1CoreDeviceManager')

logger = setup_logging()

# System Constants
class SystemConstants:
    """System-wide constants from SRS requirements"""
    
    # Memory requirements (CORE-001 to CORE-004)
    MIN_RAM_GB = 1
    MIN_BOOT_FLASH_MB = 128
    MIN_PROGRAM_FLASH_MB = 500
    
    # Power thresholds
    VOLTAGE_12V_MIN = 9.0
    VOLTAGE_12V_MAX = 32.0
    VOLTAGE_24V_MIN = 18.0
    VOLTAGE_24V_MAX = 32.0
    
    # Temperature limits (CORE-126)
    TEMP_MIN_C = -40
    TEMP_MAX_C = 70
    TEMP_MAX_DESIRED_C = 75
    
    # POST timing (CORE-020)
    POST_MAX_DURATION_SEC = 10
    
    # Communication timeouts
    MIDDLEWARE_TIMEOUT_SEC = 5
    OTA_CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    
    # File paths
    CONFIG_DIR = Path('/etc/c1core')
    DATA_DIR = Path('/var/lib/c1core')
    LOG_DIR = Path('/var/log/c1core')


class SystemState(Enum):
    """System operational states as defined in DEVMGMT requirements"""
    ACTIVE = "active"
    LOW_POWER = "low_power"
    INTERNAL_BATTERY_ONLY = "internal_battery_only"
    STORAGE_MODE = "storage_mode"
    SHUTDOWN = "shutdown"
    POST_RUNNING = "post_running"


class ResetReason(Enum):
    """System reset reasons - DEVMGMT-017"""
    POWER_ON_RESET = "power_on_reset"
    COMMANDED_RESET = "commanded_reset"
    UNEXPECTED_RESET = "unexpected_reset"
    WATCHDOG_RESET = "watchdog_reset"
    THERMAL_RESET = "thermal_reset"


class WakeUpSignal(Enum):
    """Wake-up signal types - DEVMGMT-SYS-002"""
    CAN1_ACTIVITY = "can1_activity"
    CAN2_ACTIVITY = "can2_activity"
    POWER_SOURCE_SWITCH = "power_source_switch"
    IGNITION_TOGGLE = "ignition_toggle"
    RTC_ALARM = "rtc_alarm"
    SMS_RECEIVED = "sms_received"
    ETHERNET_AUTO_ACTIVITY = "ethernet_auto_activity"
    ETHERNET_IND_ACTIVITY = "ethernet_ind_activity"
    WIFI_ACTIVITY = "wifi_activity"
    BLUETOOTH_WAKE = "bluetooth_wake"
    BATTERY_CHARGER_ALARM = "battery_charger_alarm"
    CRYO_TIMER = "cryo_timer"


class PowerLevel(IntEnum):
    """Power consumption levels in microAmps - DEVMGMT-SYS-001"""
    ACTIVE_MAX = 2000000      # 2A typical operational
    LOW_POWER_MAX = 500       # 500μA
    INTERNAL_BATTERY_MAX = 250 # 250μA
    STORAGE_MODE_MAX = 100    # 100μA


class DiagnosticLevel(Enum):
    """Diagnostic test levels - CORE-025"""
    BASIC = "basic"
    MEDIUM = "medium"
    ADVANCED = "advanced"


@dataclass
class SystemHealth:
    """System health monitoring data"""
    cpu_usage: float
    memory_usage: float
    cpu_temperature: float
    external_voltage: float
    internal_battery_level: float
    power_consumption_ua: int
    uptime_seconds: int
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def is_healthy(self) -> bool:
        """Check if system is within healthy parameters"""
        return (
            self.cpu_usage < 90 and
            self.memory_usage < 85 and
            self.cpu_temperature < SystemConstants.TEMP_MAX_C and
            self.external_voltage > SystemConstants.VOLTAGE_12V_MIN and
            self.internal_battery_level > 20
        )


@dataclass
class InterfaceStatus:
    """Interface connectivity status"""
    name: str
    connected: bool
    last_activity: Optional[datetime]
    fault_reason: Optional[str] = None
    data_rate_bps: Optional[int] = None
    error_count: int = 0
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        if self.last_activity:
            result['last_activity'] = self.last_activity.isoformat()
        return result


@dataclass
class ContainerInfo:
    """Docker container information"""
    name: str
    status: str
    essential: bool
    memory_usage_mb: float
    storage_usage_mb: float
    cpu_usage: float
    start_time: datetime
    restart_count: int = 0
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['start_time'] = self.start_time.isoformat()
        return result


class POSTResult:
    """Power-On Self Test results - CORE-010 to CORE-023"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
        self.failures = []
        self.duration = 0.0
        self.timestamp = datetime.now()
        self.test_id = str(uuid.uuid4())
    
    def add_test_result(self, test_name: str, passed: bool, details: str = "", 
                       measurement: Optional[float] = None):
        """Add individual test result"""
        test_result = {
            'name': test_name,
            'passed': passed,
            'details': details,
            'measurement': measurement,
            'timestamp': datetime.now().isoformat()
        }
        
        self.test_results.append(test_result)
        
        if passed:
            self.tests_passed += 1
            logger.info(f"POST: {test_name} PASSED - {details}")
        else:
            self.tests_failed += 1
            self.failures.append(f"{test_name}: {details}")
            logger.error(f"POST: {test_name} FAILED - {details}")
    
    def is_successful(self) -> bool:
        return self.tests_failed == 0
    
    def generate_report(self) -> Dict:
        """Generate comprehensive BOOT report - CORE-023"""
        return {
            "test_id": self.test_id,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration,
            "tests_total": self.tests_passed + self.tests_failed,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "success_rate": (self.tests_passed / max(1, self.tests_passed + self.tests_failed)) * 100,
            "test_results": self.test_results,
            "failures": self.failures,
            "success": self.is_successful()
        }


class HardwareAbstractionLayer:
    """Hardware Abstraction Layer for C1-Core hardware interfaces"""
    
    def __init__(self):
        self.logger = logger.getChild('HAL')
        self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize hardware interfaces"""
        self.logger.info("Initializing Hardware Abstraction Layer")
        # In production, this woul
