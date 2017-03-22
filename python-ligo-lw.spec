%define prefix /usr

Name: 		python-ligo-lw
Summary:	LIGO Light-Weight XML I/O Library
Version:	1.0.0
Release:	1
License:	GPL
Group:		Development/Libraries
Source:		%{name}-%{version}.tar.gz
Url:		https://git.ligo.org/kipp.cannon/python-ligo-lw
BuildRoot:	%{_tmppath}/%{name}-%{version}-root
Requires:	python-six glue glue-segments python >= 2.7
Conflicts:	glue-ligolw-tools
Provides:	glue-ligolw-tools
BuildRequires:  python-devel
Prefix:         %{prefix}
%description
The LIGO Light-Weight XML format is widely used within gravitational-wave
data analysis pipelines.  This package provides a Python library to read,
write, and interact with documents in this format.

%prep
%setup

%build
CFLAGS="%{optflags}" %{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 \
        --skip-build \
        --root=%{buildroot} \
        --prefix=%{prefix}
rm -rf $RPM_BUILD_ROOT/%{prefix}/lib*/python*/site-packages/*.egg-info

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{prefix}/bin/*
%{prefix}/lib*/python*/site-packages/ligo/lw

%changelog
*  Thu Mar 23 2017 Kipp Cannon <kipp.cannon@ligo.org>
- Initial release.
