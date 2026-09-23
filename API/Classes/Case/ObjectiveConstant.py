"""The fixed-cost term of the OSeMOSYS objective supplied with MUIO, from the data.

Only the exact supported objective and MUIO's generated parameter syntax are
accepted. For any other objective the constant is reported as unknown.
"""
import hashlib
import math
import re

OBJECTIVE_SHA256 = '234e0b03d0217e669c788b58895ce19c98f1a04d1abce8be868a20639eb085b5'


def fixed_cost(model_path, data_path):
    """Return (constant or None, explanation). No solver process or cache is used."""
    try:
        model = model_path.read_text(encoding='utf-8-sig')
        model = re.sub(r'#[^\n]*', '', model)
        objective = re.search(r'minimize\s+cost\s*:(.*?);', model, re.S)
        if not objective or hashlib.sha256(re.sub(r'\s+', '', objective[1]).encode()).hexdigest() != OBJECTIVE_SHA256:
            return None, 'Custom objective: full cost is unavailable without a supported constant evaluator.'
        data = re.sub(r'#[^\n]*', '', data_path.read_text(encoding='utf-8-sig'))
        sets = {}
        for name in ('REGION', 'TECHNOLOGY', 'YEAR'):
            found = re.search(r'\bset\s+' + name + r'\s*:=\s*(.*?);', data, re.S)
            if not found:
                raise ValueError('Missing set ' + name)
            sets[name] = found[1].split()
            if not sets[name] or any(not re.fullmatch(r'[\w.-]+', item) for item in sets[name]):
                raise ValueError('Unsupported set syntax: ' + name)
        parameters = {}
        defaults = {}
        for name in ('DiscountRate', 'ResidualCapacity', 'FixedCost'):
            found = re.search(r'\bparam\s+' + name + r'\s+default\s+([^\s:]+)\s*:=\s*(.*?);', data, re.S)
            if not found:
                raise ValueError('Unsupported or missing parameter block: ' + name)
            defaults[name] = float(found[1])
            values = {}
            region, years = None, None
            for line in found[2].splitlines():
                line = line.strip()
                if not line:
                    continue
                if name == 'DiscountRate':
                    fields = line.split()
                    if len(fields) != 2 or fields[0] not in sets['REGION']:
                        raise ValueError('Unsupported DiscountRate syntax')
                    if fields[1] != '.':
                        values[fields[0]] = float(fields[1])
                elif line.startswith('['):
                    slice_header = re.fullmatch(r'\[([^,]+),\*,\*\]\s*:', line)
                    if not slice_header or slice_header[1] not in sets['REGION']:
                        raise ValueError('Unsupported table slice')
                    region, years = slice_header[1], None
                elif line.endswith(':='):
                    years = line[:-2].split()
                    if not set(years).issubset(sets['YEAR']):
                        raise ValueError('Unexpected years')
                else:
                    fields = line.split()
                    if region is None or years is None or len(fields) != len(years) + 1 or fields[0] not in sets['TECHNOLOGY']:
                        raise ValueError('Unsupported table row')
                    for year, value in zip(years, fields[1:]):
                        if value != '.':
                            values[region, fields[0], year] = float(value)
            parameters[name] = values
        first = min(float(y) for y in sets['YEAR'])
        terms = []
        for region in sets['REGION']:
            rate = parameters['DiscountRate'].get(region, defaults['DiscountRate'])
            if not math.isfinite(rate) or rate <= -1:
                raise ValueError('Invalid discount rate')
            for tech in sets['TECHNOLOGY']:
                for year in sets['YEAR']:
                    key = region, tech, year
                    residual = parameters['ResidualCapacity'].get(key, defaults['ResidualCapacity'])
                    fixed = parameters['FixedCost'].get(key, defaults['FixedCost'])
                    terms.append(residual * fixed / (1 + rate) ** (float(year) - first + 0.5))
        value = math.fsum(terms)
        if not math.isfinite(value):
            raise ValueError('Non-finite fixed cost')
        return value, 'Fixed cost evaluated directly from residual capacity, fixed cost and discount rate.'
    except (ValueError, OSError, OverflowError) as error:
        return None, 'Full cost unavailable: ' + str(error)
