<?php

/**
 * PHP version of python script main.py created by Andrzej Pietryga
 * https://github.com/Udeus/Zabbix-Update-All-Templates
 *
 * Tested on Debian 12 with Debian supplied php-8.2 packages and Zabbix 7.4.x
 *
 * Requires these php packages/extensions:
 * - php8.2-curl
 * - php8.2-yaml
 * - php8.2-zip
 *
 * Uses the same methods as the pythong script to set the zabbix api url & key
 * - ENV File
 * - ENV Variables
 * - COMMAND LINE
 *
 */


// --- LOAD .env FILE if exists
$envFilepath = '.env';
if (file_exists($envFilepath)) {
	$env = file_get_contents($envFilepath);
	$lines = explode("\n",$env);

	foreach ($lines as $line) {
		preg_match("/([^#]+)=(.*)/",$line,$matches);
		if (isset($matches[2])) {
			putenv(trim($line));
		}
	}
}

// --- CONFIGURATION ---
// Replace with your Zabbix URL and API Token or set them as environment variables.
$api_url = getenv('ZABBIX_URL') ?: '';
$api_token = getenv('ZABBIX_API_TOKEN') ?: '';

$commandsList = [
	"help" => "Show all commands",
	"template list" => "Show all templates and ID",
	"template update" => "Update one template",
	"template update all" => "Update all templates",
	"backup create" => "Create backup of one template",
	"backup create all" => "Create backup of all templates",
	"backup list" => "Show list of all backups",
	"backup restore" => "Restore selected backup",
	"backup delete" => "Delete selected backup",
	"about" => "About script",
	"exit" => "Close script"
];

$scriptInfo = [
	["Version", "1.0"],
	["Author", "Andrzej Pietryga"],
	["Contact", "https://github.com/Udeus"],
	["License", "GPL-3.0"],
	["Repository", "https://github.com/Udeus/Zabbix-Update-All-Templates"]
];

// --- ARGUMENT PARSING ---
$options = getopt("u:t:", ["url:", "token:", "update", "no-verify"]);

$verifySsl = !isset($options['no-verify']);
$updateAll = isset($options['update']);
$zabbixVersion = null;
$terminalWidth = exec('tput cols') ?: 80;


// --- UTILITY FUNCTIONS (from utils.py) ---
/**
 * Retrieves a configuration value from an environment variable, an argument, or user input.
 *
 * @param string      $envVar       The name of the environment variable.
 * @param string|null $argValue     An optional value passed as an argument.
 * @param string|null $inputPrompt  An optional prompt for user input.
 *
 * @return string The configuration value.
 *
 * @throws ValueError If the configuration value is not found.
 */
function getConfigValue(string $envVar, ?string $argValue = null, ?string $inputPrompt = null): string
{
	$value = getenv($envVar);

	if ($value) {
		return trim($value);
	}

	if ($argValue) {
		return trim($argValue);
	}

	if ($inputPrompt) {
		echo $inputPrompt;
		$handle = fopen("php://stdin", 'rb');
		$input = trim(fgets($handle));
		fclose($handle);
		return $input;
	}

	throw new ValueError("Configuration value for '{$envVar}' is missing.");
}


/**
 * Gets the next available backup ID.
 *
 * @return int The next backup ID.
 */
function getNextBackupId(): int
{
	if (!is_dir('backups')) {
		return 1;
	}

	$existingBackups = [];
	$dirnames = scandir('backups');

	foreach ($dirnames as $dirname) {
		if ($dirname === '.' || $dirname === '..') {
			continue;
		}

		if (str_contains($dirname, '-') !== false) {
			$parts = explode('-', $dirname);
			try {
				$backupId = (int)$parts[0];
				$existingBackups[] = $backupId;
			} catch (Exception $e) {
				continue;
			}
		}
	}

	return empty($existingBackups) ? 1 : max($existingBackups) + 1;
}

/**
 * Formats a URL to point to the Zabbix API endpoint.
 *
 * @param string $url The base URL.
 *
 * @return string The formatted Zabbix API URL.
 */
function zabbixUrl(string $url): string
{
	if (!str_ends_with($url, '/api_jsonrpc.php')) {
		if (!str_ends_with($url, '/')) {
			$url .= '/';
		}
		$url .= 'api_jsonrpc.php';
	}

	if (!preg_match('#^https?://#', $url)) {
		$url = "https://{$url}";
	}

	return $url;
}


/**
 * Reads a YAML file, converts it to JSON, and then double-encodes it.
 *
 * @param string $filename The path to the YAML file.
 *
 * @return string A JSON string.
 */
function getFile(string $filename): string
{
	if (!file_exists($filename)) {
		throw new RuntimeException("File not found: {$filename}");
	}

	$yamlContent = file_get_contents($filename);
	$data = yaml_parse($yamlContent);
	$jsonData = json_encode($data, JSON_THROW_ON_ERROR);
	return json_encode($jsonData, JSON_THROW_ON_ERROR);
}

// --- CORE LOGIC ---
$api_url = zabbixUrl(getConfigValue('ZABBIX_URL', $options['url'] ?? null, "Zabbix URL address: "));
$api_token = getConfigValue('ZABBIX_API_TOKEN', $options['token'] ?? null, "Zabbix API token: ");

// Basic logging function
function logAction($message, $level = 'INFO'): void
{
	$timestamp = date("Y-m-d H:i");
	$logFile = fopen("actions.log", 'ab');
	fwrite($logFile, "[{$timestamp}][{$level}] {$message}\n");
	fclose($logFile);
}

function connectApi($data, $header = null)
{
	global $api_url, $api_token, $verifySsl, $zabbixVersion;

	if ($zabbixVersion == '6.0') {
		$header = ['Content-Type: application/json-rpc'];
		$data = json_decode($data, true, 512, JSON_THROW_ON_ERROR);
		$data['auth'] = $api_token;
		$data = json_encode($data, JSON_THROW_ON_ERROR);
	} elseif (!$header) {
		$header = ['Authorization: Bearer ' . $api_token, 'Content-Type: application/json-rpc'];
	}

	$ch = curl_init();
	curl_setopt($ch, CURLOPT_URL, $api_url);
	curl_setopt($ch, CURLOPT_POST, true);
	curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
	curl_setopt($ch, CURLOPT_HTTPHEADER, $header);
	curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

	if (!$verifySsl) {
		curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
		curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
	}

	$response = curl_exec($ch);

	if (curl_errno($ch)) {
		logAction("cURL error: " . curl_error($ch), 'ERROR');
		echo "Error API: " . curl_error($ch) . "\n";
		exit(1);
	}

	curl_close($ch);

	$responseData = json_decode($response, true, 512, JSON_THROW_ON_ERROR);

	if (isset($responseData['error'])) {
		$error = $responseData['error'];
		logAction("API error: " . json_encode($error, JSON_THROW_ON_ERROR), 'ERROR');
		echo "API error: " . $error['message'] . "\n";
		exit(1);
	}

	return $responseData['result'];
}

try {
	$data = '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}';
	$header = ['Content-Type: application/json-rpc'];

	$zabbixVersion = connectApi($data, $header);
	preg_match("/^(\d\.\d)/", $zabbixVersion, $matches);
	$zabbixVersion = $matches[1] ?? null;

	if (!$zabbixVersion) {
		throw new RuntimeException("Could not determine Zabbix version.");
	}
} catch (Exception $e) {
	logAction("Initialization error: " . $e->getMessage(), 'ERROR');
	echo "Error: " . $e->getMessage() . "\n";
	exit(1);
}

// Check API Token
try {
	$data = '{"jsonrpc": "2.0","method": "token.get","params": {"output": "extend"},"id": 1}';
	$header = ['Authorization: Bearer ' . $api_token, 'Content-Type: application/json-rpc'];
	connectApi($data, $header);
} catch (Exception $e) {
	logAction("Error API: Correct your token", 'ERROR');
	echo "Error API: Correct your token\n";
	exit(1);
}

// --- COMMAND FUNCTIONS ---

function getTemplates(): void
{
	$api_date = '{"jsonrpc": "2.0","method": "template.get","params": {"output": ["name", "groupid"]},"id": 1}';
	$response = connectApi($api_date);
	// Simple table-like printout for demonstration
	echo "templateid\tname\t\tgroupid\n";
	echo "------------------------------------------------------\n";
	foreach ($response as $item) {
		echo sprintf("%s\t\t%s\n", $item['templateid'], $item['name']);
	}
}

function createOneBackup(): void
{
	echo "Template ID: ";
	$template_id = trim(fgets(STDIN));

	$api_date = '{"jsonrpc": "2.0","method": "template.get","params": {"output": ["name"],"templateids": "' . $template_id . '"},"id": 1}';
	$template_name = connectApi($api_date)[0]['name'];

	$api_date = '{"jsonrpc": "2.0","method": "configuration.export","params": {"options": {"templates": ["' . $template_id . '"]},"format": "yaml"},"id": 1}';
	$response = connectApi($api_date);

	$backup_id = getNextBackupId();
	$date_create = date("d.m.Y");
	$time_create = date("H.i");
	$backup_path = "backups/{$backup_id}-{$date_create}-{$time_create}";

	if (!is_dir($backup_path)) {
		if (!mkdir($backup_path, 0750, true) && !is_dir($backup_path)) {
			throw new RuntimeException(sprintf('Directory "%s" was not created', $backup_path));
		}
	}

	file_put_contents("{$backup_path}/{$template_name}.yaml", $response);

	logAction("Backup {$template_name} template created");
	echo "Backup template {$template_name} created\n";
}

function createBackups(): void
{
	$api_date = '{"jsonrpc": "2.0","method": "template.get","params": {"output": ["name", "groupid"]},"id": 1}';
	$resp_template_list = connectApi($api_date);

	$template_number = 1;
	$list_length = count($resp_template_list);

	$backup_id = getNextBackupId();
	$date_create = date("d.m.Y");
	$time_create = date("H.i");
	$backup_path = "backups/{$backup_id}-{$date_create}-{$time_create}";

	if (!is_dir($backup_path)) {
		if (!mkdir($backup_path, 0750, true) && !is_dir($backup_path)) {
			throw new RuntimeException(sprintf('Directory "%s" was not created', $backup_path));
		}
	}

	foreach ($resp_template_list as $item) {
		$template_id = $item['templateid'];
		$template_name = $item['name'];

		$api_date = '{"jsonrpc": "2.0","method": "configuration.export","params": {"options": {"templates": ["' . $template_id . '"]},"format": "yaml"},"id": 1}';
		$response = connectApi($api_date);

		echo "{$template_number}/{$list_length}\n";
		$template_number++;

		file_put_contents("{$backup_path}/{$template_name}.yaml", $response);
	}

	logAction("All backups created");
	echo "All backups created\n";
}

function listBackups(): void
{
	$backups_list = [];
	$backups_dir = 'backups';

	if (!is_dir($backups_dir)) {
		echo "No backups found\n";
		return;
	}

	$dirs = scandir($backups_dir);
	sort($dirs);

	foreach ($dirs as $dir) {
		if ($dir === '.' || $dir === '..') {
			continue;
		}

		$backup_path = "{$backups_dir}/{$dir}";

		if (is_dir($backup_path)) {
			try {
				$parts = explode('-', $dir);
				if (count($parts) === 3) {
					$backup_id = $parts[0];
					$date = $parts[1];
					$time = $parts[2];
					$templates_count = count(glob("{$backup_path}/*.yaml"));
					$backups_list[] = [$backup_id, $date, $time, $templates_count];
				}
			} catch (Exception $e) {
				continue;
			}
		}
	}

	if (empty($backups_list)) {
		echo "No backups found\n";
	} else {
		// Simple table-like printout
		echo "ID\tDate\t\tTime\tTemplates count\n";
		echo "----------------------------------------------\n";
		foreach ($backups_list as $backup) {
			echo implode("\t", $backup) . "\n";
		}
	}
}

function deleteBackup(): void
{
	listBackups();
	echo "Enter backup ID to delete: ";
	$backup_id = trim(fgets(STDIN));

	$backup_to_delete = null;
	$backups_dir = 'backups';

	if (!is_dir($backups_dir)) {
		echo "No backups found\n";
		return;
	}

	foreach (scandir($backups_dir) as $dir) {
		if (str_starts_with($dir, "{$backup_id}-")) {
			$backup_to_delete = $dir;
			break;
		}
	}

	if ($backup_to_delete === null) {
		echo "Backup with ID {$backup_id} not found. Use 'backup list' to see available backups.\n";
		return;
	}

	echo "Are you sure you want to delete backup {$backup_to_delete}? (yes/no): ";
	$confirmation = trim(fgets(STDIN));

	if (strtolower($confirmation) === 'yes') {
		try {
			$backup_path = "{$backups_dir}/{$backup_to_delete}";
			if (is_dir($backup_path)) {
				$files = glob("{$backup_path}/*");
				foreach ($files as $file) {
					if (is_file($file)) {
						unlink($file);
					}
				}
				rmdir($backup_path);
			}

			echo "Backup {$backup_to_delete} has been deleted\n";
			logAction("Deleted backup {$backup_to_delete}");
		} catch (Exception $e) {
			echo "Error occurred while deleting backup: " . $e->getMessage() . "\n";
			logAction("Error deleting backup {$backup_to_delete}: " . $e->getMessage(), 'ERROR');
		}
	} else {
		echo "Backup deletion cancelled\n";
	}
}

function restoreBackup(): void
{
	listBackups();
	echo "Enter backup ID to restore: ";
	$backup_id = trim(fgets(STDIN));

	$backup_to_restore = null;
	$backups_dir = 'backups';

	if (!is_dir($backups_dir)) {
		echo "No backups found\n";
		return;
	}

	foreach (scandir($backups_dir) as $dir) {
		if (str_starts_with($dir, "{$backup_id}-")) {
			$backup_to_restore = $dir;
			break;
		}
	}

	if ($backup_to_restore === null) {
		echo "Backup with ID {$backup_id} not found. Use 'backup list' to see available backups.\n";
		return;
	}

	$backup_path = "{$backups_dir}/{$backup_to_restore}";
	if (!is_dir($backup_path)) {
		echo "Backup directory does not exist: {$backup_path}\n";
		return;
	}

	echo "Are you sure you want to restore backup {$backup_to_restore}? (yes/no): ";
	$confirmation = trim(fgets(STDIN));

	if (strtolower($confirmation) === 'yes') {
		try {
			$files = glob("{$backup_path}/*.yaml");
			foreach ($files as $file) {
				updateTemplate($file);
				echo "Restored template: " . basename($file) . "\n";
			}

			echo "Successfully restored backup {$backup_to_restore}\n";
			logAction("Restored backup {$backup_to_restore}");
		} catch (Exception $e) {
			echo "Error occurred while restoring backup: " . $e->getMessage() . "\n";
			logAction("Error restoring backup {$backup_to_restore}: " . $e->getMessage(), 'ERROR');
		}
	} else {
		echo "Backup restoration cancelled\n";
	}
}

function updateTemplate($filename): void
{
	echo "Update: {$filename}\n";
	$data_file = getFile($filename);
	$api_date = '{"jsonrpc": "2.0","method": "configuration.import","params": {"format": "json","rules": {"templates": {"createMissing": true,"updateExisting": true},"items": {"createMissing": true,"updateExisting": true,"deleteMissing": true},"triggers": {"createMissing": true,"updateExisting": true,"deleteMissing": true},"valueMaps": {"createMissing": true,"updateExisting": false}},"source": ' . $data_file . '},"id": 1}';
	connectApi($api_date);
}

function downloadTemplates(): void
{
	global $zabbixVersion;

	echo "Downloading all templates for Zabbix...\n";

	$repoUrl = "https://git.zabbix.com/rest/api/latest/projects/ZBX/repos/zabbix/archive?at=refs%2Fheads%2Frelease%2F{$zabbixVersion}&format=zip";
	$nameZipFile = "zabbix.zip";

	if (is_dir('templates')) {
		exec("rm -rf templates");
	}

	try {
		copy($repoUrl, $nameZipFile);

		$zip = new ZipArchive;
		if ($zip->open($nameZipFile) === TRUE) {
			$zip->extractTo('tmp/');
			$zip->close();

			rename("tmp/templates", "templates");
			exec("rm -rf tmp");
			unlink($nameZipFile);
		} else {
			throw new RuntimeException('Failed to open zip file.');
		}
	} catch (Exception $e) {
		logAction("Error downloading templates: " . $e->getMessage(), 'ERROR');
		echo "Error downloading templates: " . $e->getMessage() . "\n";
	}
}

function updateAllTemplate(): void
{
	$dir = new RecursiveDirectoryIterator('templates');
	$it = new RecursiveIteratorIterator($dir);

	foreach ($it as $file) {
		if ($file->isDir() || !str_ends_with($file->getFilename(), '.yaml')) {
			continue;
		}
		updateTemplate($file->getPathname());
	}

	logAction("Updated all templates");
	echo "All templates updated\n";
}

function updateOneTemplate(): void
{
	echo "Template Name: ";
	$template_name = trim(fgets(STDIN));
	$full_template_name = 'name: \'' . $template_name . '\'';

	$dir = new RecursiveDirectoryIterator('templates');
	$it = new RecursiveIteratorIterator($dir);

	foreach ($it as $file) {
		if ($file->isDir() || !str_ends_with($file->getFilename(), '.yaml')) {
			continue;
		}

		$filePath = $file->getPathname();

		try {
			$content = file_get_contents($filePath);
			if (str_contains($content, $full_template_name) !== false) {
				updateTemplate($filePath);
			}
		} catch (Exception $e) {
			logAction("Error file {$filePath}: " . $e->getMessage(), 'ERROR');
			echo "Error file {$filePath}: " . $e->getMessage() . "\n";
		}
	}

	logAction("Updated template {$template_name}");
	echo "Updated template {$template_name}\n";
}

function helpCommand(): void
{
	global $commandsList;
	echo "Command\t\tDescription\n";
	echo "------------------------------------------------------\n";
	foreach ($commandsList as $command => $description) {
		echo sprintf("%s\t\t%s\n", $command, $description);
	}
	echo "How to use: https://github.com/Udeus/Zabbix-Update-All-Templates\n";
}

function printAbout(): void
{
	global $scriptInfo;
	echo "-----------------------------------\n";
	foreach ($scriptInfo as $info) {
		echo sprintf("%s\t\t%s\n", $info[0], $info[1]);
	}
	echo "-----------------------------------\n";
}

function exitScript(): void
{
	echo "Closing the script...\n";
	if (is_dir('templates')) {
		exec("rm -rf templates");
	}
	exit();
}

$commands = [
	'help' => 'helpCommand',
	'template list' => 'getTemplates',
	'template update' => 'updateOneTemplate',
	'template update all' => 'updateAllTemplate',
	'backup create' => 'createOneBackup',
	'backup create all' => 'createBackups',
	'backup list' => 'listBackups',
	'backup restore' => 'restoreBackup',
	'backup delete' => 'deleteBackup',
	'about' => 'printAbout',
	'exit' => 'exitScript'
];

function executeCommand(): void
{
	global $commands;
	echo "Command: ";
	$command = trim(fgets(STDIN));
	$action = $commands[strtolower($command)] ?? null;

	if ($action) {
		call_user_func($action);
	} else {
		echo "Command not found. Type 'help' to see available commands.\n";
	}
}

// --- MAIN EXECUTION ---
if (!empty($api_url) && !empty($api_token)) {
	downloadTemplates();
	helpCommand();

	if ($updateAll) {
		updateAllTemplate();
		exit();
	}

	while (true) {
		executeCommand();
	}
}