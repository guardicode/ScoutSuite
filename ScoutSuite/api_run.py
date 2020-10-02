import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor

from ScoutSuite.core.console import print_exception
from ScoutSuite.core.exceptions import RuleExceptions
from ScoutSuite.core.processingengine import ProcessingEngine
from ScoutSuite.core.ruleset import Ruleset
from ScoutSuite.output.html import ScoutReport
from ScoutSuite.providers import get_provider
from ScoutSuite.providers.base.authentication_strategy_factory import get_authentication_strategy
from asyncio_throttle import Throttler


def run(provider,
        # AWS
        profile=None,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_session_token=None,
        # Azure
        user_account=False, service_account=None,
        cli=False, msi=False, service_principal=False, file_auth=None,
        tenant_id=None, subscription_id=None,
        client_id=None, client_secret=None,
        username=None, password=None,
        # GCP
        project_id=None, folder_id=None, organization_id=None, all_projects=False,
        timestamp=False,
        services=[], skipped_services=[],
        max_workers=10,
        regions=[],
        excluded_regions=[],
        fetch_local=False, update=False,
        max_rate=None,
        ip_ranges=[], ip_ranges_name_key='name',
        ruleset='default.json', exceptions=None,
        force_write=False,
        debug=False,
        quiet=False,
        no_browser=False,
        programmatic_execution=True):
    """
    Run a scout job in an async event loop from any codebase.
    """
    loop = asyncio.new_event_loop()
    loop.throttler = Throttler(rate_limit=max_rate if max_rate else 999999, period=1)
    asyncio.set_event_loop(loop)
    loop.set_default_executor(ThreadPoolExecutor(max_workers=max_workers))
    result = loop.run_until_complete(_run(**locals()))  # pass through all the parameters
    loop.close()
    return result


async def _run(provider,
               # AWS
               profile,
               aws_access_key_id,
               aws_secret_access_key,
               aws_session_token,
               # Azure
               user_account, service_account,
               cli, msi, service_principal, file_auth,
               tenant_id, subscription_id,
               client_id, client_secret,
               username, password,
               # GCP
               project_id, folder_id, organization_id, all_projects,
               timestamp,
               services, skipped_services,
               max_workers,
               regions,
               excluded_regions,
               fetch_local, update,
               max_rate,
               ip_ranges, ip_ranges_name_key,
               ruleset, exceptions,
               force_write,
               debug,
               quiet,
               no_browser,
               programmatic_execution,
               **kwargs):
    """
    Run a scout job.
    """

    auth_strategy = get_authentication_strategy(provider)
    try:
        credentials = auth_strategy.authenticate(profile=profile,
                                                 aws_access_key_id=aws_access_key_id,
                                                 aws_secret_access_key=aws_secret_access_key,
                                                 aws_session_token=aws_session_token,
                                                 user_account=user_account,
                                                 service_account=service_account,
                                                 cli=cli,
                                                 msi=msi,
                                                 service_principal=service_principal,
                                                 file_auth=file_auth,
                                                 tenant_id=tenant_id,
                                                 subscription_id=subscription_id,
                                                 client_id=client_id,
                                                 client_secret=client_secret,
                                                 username=username,
                                                 password=password,
                                                 access_key_id=None,
                                                 access_key_secret=None,
                                                 programmatic_execution=programmatic_execution)

        if not credentials:
            # TODO figure out how to display these kinds of errors on island
            return {'error': "Credentials failed"}
    except Exception as e:
        print_exception('Authentication failure: {}'.format(e))
        return {'error': f"Exception {e}"}

    # Create a cloud provider object
    cloud_provider = get_provider(provider=provider,
                                  profile=profile,
                                  project_id=project_id,
                                  folder_id=folder_id,
                                  organization_id=organization_id,
                                  all_projects=all_projects,
                                  report_dir=None,
                                  timestamp=timestamp,
                                  services=services,
                                  skipped_services=skipped_services,
                                  credentials=credentials)

    # Create a new report
    report_name = cloud_provider.get_report_name()
    report = ScoutReport(cloud_provider.provider_code,
                         report_name,
                         './',
                         timestamp,
                         result_format='json')

    # Complete run, including pulling data from provider
    if not fetch_local:
        # Fetch data from provider APIs
        try:
            # Gathering data from APIs
            await cloud_provider.fetch(regions=regions, excluded_regions=excluded_regions)
        except KeyboardInterrupt:
            # nCancelled by user
            return 130

        # Update means we reload the whole config and overwrite part of it
        if update:
            # Updating existing data
            current_run_services = copy.deepcopy(cloud_provider.services)
            last_run_dict = report.encoder.load_from_file('RESULTS')
            cloud_provider.services = last_run_dict['services']
            for service in cloud_provider.service_list:
                cloud_provider.services[service] = current_run_services[service]

    # Partial run, using pre-pulled data
    else:
        # Using local data
        # Reload to flatten everything into a python dictionary
        last_run_dict = report.encoder.load_from_file('RESULTS')
        for key in last_run_dict:
            setattr(cloud_provider, key, last_run_dict[key])

    # Pre processing
    cloud_provider.preprocessing(
        ip_ranges, ip_ranges_name_key)

    # Analyze config
    # Running rule engine
    finding_rules = Ruleset(cloud_provider=cloud_provider.provider_code,
                            environment_name=cloud_provider.environment,
                            filename=ruleset,
                            ip_ranges=ip_ranges,
                            account_id=cloud_provider.account_id)
    processing_engine = ProcessingEngine(finding_rules)
    processing_engine.run(cloud_provider)

    # Create display filters
    # Applying display filters
    filter_rules = Ruleset(cloud_provider=cloud_provider.provider_code,
                           environment_name=cloud_provider.environment,
                           rule_type='filters',
                           account_id=cloud_provider.account_id)
    processing_engine = ProcessingEngine(filter_rules)
    processing_engine.run(cloud_provider)

    # Handle exceptions
    if exceptions:
        # Applying exceptions
        try:
            exceptions = RuleExceptions(exceptions)
            exceptions.process(cloud_provider)
            exceptions = exceptions.exceptions
        except Exception as e:
            print_exception('Failed to load exceptions: {}'.format(e))
            exceptions = {}
    else:
        exceptions = {}

    run_parameters = {
        'services': services,
        'skipped_services': skipped_services,
        'regions': regions,
        'excluded_regions': excluded_regions,
    }
    # Finalize
    cloud_provider.postprocessing(report.current_time, finding_rules, run_parameters)

    cloud_provider.credentials = None
    return cloud_provider
